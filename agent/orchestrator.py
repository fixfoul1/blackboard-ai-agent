"""
Main session orchestrator coordinating browser automation, audio recording,
and AI summarization into a single unified workflow.
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Dict, Any

from agent.config import Config
from agent.browser import BrowserManager
from agent.recorder import AudioRecorder
from agent.blackboard import BlackboardAgent
from agent.summarizer import LectureSummarizer

logger = logging.getLogger("agent.orchestrator")

class SessionOrchestrator:
    def __init__(
        self,
        student_name: str = Config.STUDENT_NAME,
        headless: bool = Config.HEADLESS,
        record_video: bool = True,
    ):
        self.student_name = student_name
        self.headless = headless
        self.record_video = record_video
        self.is_running = False
        self._stop_event = asyncio.Event()

        self.browser_manager: Optional[BrowserManager] = None
        self.audio_recorder: Optional[AudioRecorder] = None
        self.blackboard_agent: Optional[BlackboardAgent] = None
        self.summarizer = LectureSummarizer()

    async def run(
        self,
        session_url: str,
        duration_minutes: Optional[int] = None,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """Run the complete join -> record -> summarize workflow."""
        self.is_running = True
        self._stop_event.clear()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"class_{timestamp}"
        audio_path = Config.RECORDINGS_DIR / f"{base_name}.webm"

        video_dir = Config.RECORDINGS_DIR if self.record_video else None

        def notify(msg: str):
            logger.info(msg)
            if status_callback:
                status_callback(msg)

        notify(f"Starting session at {timestamp}...")

        self.browser_manager = BrowserManager(
            headless=self.headless,
            record_video_dir=video_dir,
        )

        try:
            # 1. Launch Browser
            notify("Launching Chromium browser...")
            page = await self.browser_manager.start()

            # 2. Attach in-page Audio Recorder
            self.audio_recorder = AudioRecorder(audio_path)
            await self.audio_recorder.attach_to_page(page)

            # 3. Join Blackboard Session
            notify(f"Joining Blackboard session as '{self.student_name}'...")
            self.blackboard_agent = BlackboardAgent(page, student_name=self.student_name)
            joined = await self.blackboard_agent.join_session(session_url)

            if not joined:
                notify("Warning: Could not automatically detect in-room state; continuing to record.")
            else:
                notify("Connected to room! Class is now being recorded.")

            # 4. Start Audio Recording
            await self.audio_recorder.start(page)

            # 5. Monitoring loop
            start_time = asyncio.get_event_loop().time()
            max_seconds = duration_minutes * 60 if duration_minutes else None

            while not self._stop_event.is_set():
                elapsed = int(asyncio.get_event_loop().time() - start_time)
                elapsed_min = elapsed // 60
                elapsed_sec = elapsed % 60

                if max_seconds and elapsed >= max_seconds:
                    notify(f"Scheduled duration of {duration_minutes}m reached. Concluding session...")
                    break

                # Check if session ended on Blackboard
                status = await self.blackboard_agent.check_session_status()
                if not status["active"]:
                    notify(f"Blackboard session concluded: {status['reason']}. Stopping recording...")
                    break

                # Sleep in short increments to stay responsive to stop events
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=5)
                except asyncio.TimeoutError:
                    pass

            notify("Stopping recording and finalizing audio file...")
            await self.audio_recorder.stop(page)

        finally:
            notify("Closing browser...")
            await self.browser_manager.close()
            self.is_running = False

        # 6. Generate AI Summary
        notify("Generating AI Summary using Google Gemini...")
        summary_result = self.summarizer.summarize_audio(audio_path)
        summary_file = self.summarizer.save_summary(summary_result, base_name)
        notify(f"Summary saved to {summary_file}")

        return {
            "success": True,
            "audio_file": str(audio_path),
            "summary_file": str(summary_file),
            "summary_markdown": summary_result.get("markdown", ""),
            "timestamp": timestamp,
        }

    def stop(self):
        """Signal the running session to stop and begin summarization."""
        if self.is_running:
            logger.info("Manual stop requested.")
            self._stop_event.set()
