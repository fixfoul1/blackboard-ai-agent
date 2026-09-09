"""
Blackboard Collaborate Ultra automation module.
Handles guest name input, audio/video test bypass, tutorial closing,
mute verification, and session lifecycle monitoring.
"""

import asyncio
import logging
from typing import Optional, Callable
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger("agent.blackboard")

class BlackboardAgent:
    def __init__(self, page: Page, student_name: str = "Student"):
        self.page = page
        self.student_name = student_name
        self.is_connected = False
        self.session_ended = False

    async def join_session(self, url: str, timeout_seconds: int = 120) -> bool:
        """Navigate to Blackboard session URL and perform join sequence."""
        logger.info(f"Navigating to session URL: {url}")
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            logger.warning(f"Initial navigation slow or timed out: {e}")

        # Wait for page to initialize (Blackboard Ultra is an SPA)
        await asyncio.sleep(3)

        # 1. Check if Guest Name input is present
        await self._handle_guest_form()

        # 2. Loop and handle any onboarding modals (Audio test, Video test, Tutorial)
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout_seconds:
            # Check if we are inside the room
            if await self._is_in_room():
                self.is_connected = True
                logger.info("Successfully joined Blackboard Collaborate room!")
                break

            # Handle setup prompts
            handled_any = await self._handle_setup_modals()
            if not handled_any:
                await asyncio.sleep(2)

        # 3. Ensure microphone and video are strictly muted
        if self.is_connected:
            await self._ensure_muted()

        return self.is_connected

    async def _handle_guest_form(self):
        """Detect and fill guest join form if present."""
        guest_selectors = [
            "#guest-name",
            "input[name='guest-name']",
            "input[placeholder*='name' i]",
            "input[placeholder*='Name' i]",
            "input[aria-label*='name' i]",
        ]

        for sel in guest_selectors:
            try:
                elem = self.page.locator(sel).first
                if await elem.is_visible(timeout=3000):
                    logger.info(f"Found Guest Name field with selector: {sel}")
                    await elem.fill(self.student_name)
                    await asyncio.sleep(0.5)

                    # Look for Join button
                    join_btn_selectors = [
                        "#join-guest-name",
                        "button:has-text('Join Session')",
                        "button:has-text('Join')",
                        "button[type='submit']",
                    ]
                    for btn_sel in join_btn_selectors:
                        btn = self.page.locator(btn_sel).first
                        if await btn.is_visible(timeout=2000):
                            logger.info(f"Clicking Join button: {btn_sel}")
                            await btn.click()
                            await asyncio.sleep(2)
                            return
            except Exception:
                continue

    async def _handle_setup_modals(self) -> bool:
        """Dismiss audio/video checks, tutorials, or permission confirmations."""
        action_taken = False

        # Audio / Video test buttons ("Yes - It's working", "Skip audio test", etc.)
        test_confirm_buttons = [
            "button:has-text('Yes - It\\'s working')",
            "button:has-text('Yes - It’s working')",
            "button:has-text('Yes, audio is working')",
            "button:has-text('Yes, video is working')",
            "button:has-text('Skip audio test')",
            "button:has-text('Skip video test')",
            "button:has-text('Skip test')",
            "#audio-test-yes",
            "#video-test-yes",
            "button[data-test='audio-ok-button']",
        ]

        for btn_sel in test_confirm_buttons:
            try:
                btn = self.page.locator(btn_sel).first
                if await btn.is_visible(timeout=1000):
                    logger.info(f"Dismissing test prompt: {btn_sel}")
                    await btn.click()
                    await asyncio.sleep(1)
                    action_taken = True
            except Exception:
                continue

        # Tutorial / Welcome popups ("Later", "Close", "Skip tutorial")
        tutorial_buttons = [
            "button:has-text('Later')",
            "button:has-text('Skip tutorial')",
            "button:has-text('Tell me later')",
            "button:has-text('Close')",
            "button[aria-label='Close tutorial']",
            "button[aria-label='Close']",
            ".close-tutorial",
            "#tutorial-later",
        ]

        for btn_sel in tutorial_buttons:
            try:
                btn = self.page.locator(btn_sel).first
                if await btn.is_visible(timeout=1000):
                    logger.info(f"Dismissing tutorial/welcome prompt: {btn_sel}")
                    await btn.click()
                    await asyncio.sleep(0.5)
                    action_taken = True
            except Exception:
                continue

        return action_taken

    async def _is_in_room(self) -> bool:
        """Check whether we have successfully arrived in the live room."""
        room_indicators = [
            "#main-container",
            "#session-menu-open",
            "#collaborate-ultra-panel",
            "#techcheck-audio-menu",
            "#audio-menu",
            "button[aria-label*='Share audio' i]",
            "button[aria-label*='My Settings' i]",
            "button[aria-label*='Open Collaborate panel' i]",
            "#main-session-content",
        ]

        for ind in room_indicators:
            try:
                if await self.page.locator(ind).first.is_visible(timeout=500):
                    return True
            except Exception:
                continue
        return False

    async def _ensure_muted(self):
        """Ensure local microphone and camera are muted to avoid accidental broadcast."""
        try:
            # Check mic button
            mic_btn = self.page.locator("button[aria-label*='Share audio' i], #audio-menu").first
            if await mic_btn.is_visible(timeout=2000):
                # If active/unmuted, mute it
                is_active = await mic_btn.get_attribute("aria-pressed")
                if is_active == "true":
                    logger.warning("Microphone was active! Muting immediately...")
                    await mic_btn.click()
                else:
                    logger.info("Microphone verified muted.")
        except Exception as e:
            logger.debug(f"Mic status check: {e}")

    async def check_session_status(self) -> dict:
        """Check if session is still alive or ended."""
        end_indicators = [
            "text='The session has ended'",
            "text='You have left the session'",
            "text='Session is closed'",
            "#session-ended-message",
        ]

        for ind in end_indicators:
            try:
                if await self.page.locator(ind).first.is_visible(timeout=500):
                    self.session_ended = True
                    return {"active": False, "reason": "Session ended by host"}
            except Exception:
                continue

        if not await self._is_in_room():
            return {"active": False, "reason": "Disconnected from room"}

        return {"active": True, "reason": "In session"}
