"""
Local FastAPI Web Application for Blackboard AI Agent.
Provides an interactive dashboard for starting/stopping sessions,
monitoring live status, viewing past recordings, and reading summaries.
"""

import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent.config import Config
from agent.orchestrator import SessionOrchestrator

app = FastAPI(title="Blackboard AI Agent Dashboard")

# Global orchestrator instance and state
active_orchestrator: Optional[SessionOrchestrator] = None
session_state: Dict[str, Any] = {
    "status": "idle", # "idle", "running", "summarizing", "completed", "error"
    "message": "Ready to join class.",
    "current_url": None,
    "start_time": None,
    "last_result": None,
}

class JoinRequest(BaseModel):
    url: str
    student_name: Optional[str] = None
    duration_minutes: Optional[int] = None
    headless: Optional[bool] = False

@app.get("/", response_class=HTMLResponse)
async def get_index():
    template_path = Config.BASE_DIR / "templates" / "index.html"
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Template not found")
    return HTMLResponse(content=template_path.read_text(encoding="utf-8"))

@app.get("/api/status")
async def get_status():
    return session_state

@app.post("/api/join")
async def start_join(req: JoinRequest, background_tasks: BackgroundTasks):
    global active_orchestrator, session_state

    if session_state["status"] in ("running", "summarizing"):
        raise HTTPException(status_code=400, detail="A session is already active.")

    student_name = req.student_name or Config.STUDENT_NAME

    active_orchestrator = SessionOrchestrator(
        student_name=student_name,
        headless=req.headless if req.headless is not None else Config.HEADLESS,
    )

    session_state["status"] = "running"
    session_state["message"] = f"Initializing browser to join as '{student_name}'..."
    session_state["current_url"] = req.url
    session_state["last_result"] = None

    def status_callback(msg: str):
        session_state["message"] = msg

    async def _run_task():
        try:
            res = await active_orchestrator.run(
                session_url=req.url,
                duration_minutes=req.duration_minutes,
                status_callback=status_callback,
            )
            session_state["status"] = "completed"
            session_state["message"] = "Session completed and summary generated!"
            session_state["last_result"] = res
        except Exception as e:
            session_state["status"] = "error"
            session_state["message"] = f"Error during session: {str(e)}"

    background_tasks.add_task(_run_task)
    return {"status": "started", "message": "Agent started joining session."}

@app.post("/api/stop")
async def stop_session():
    global active_orchestrator, session_state

    if not active_orchestrator or session_state["status"] != "running":
        raise HTTPException(status_code=400, detail="No active session to stop.")

    session_state["status"] = "summarizing"
    session_state["message"] = "Stopping recording and generating AI summary..."
    active_orchestrator.stop()

    return {"status": "stopping", "message": "Signal sent to conclude session."}

@app.get("/api/history")
async def get_history():
    """List past summaries and recordings."""
    history = []
    output_dir = Config.OUTPUT_DIR
    if output_dir.exists():
        for md_file in sorted(output_dir.glob("*_summary.md"), reverse=True):
            base = md_file.stem.replace("_summary", "")
            audio_file = Config.RECORDINGS_DIR / f"{base}.webm"
            history.append({
                "id": base,
                "summary_file": str(md_file.name),
                "has_audio": audio_file.exists(),
                "created_at": md_file.stat().st_mtime,
                "preview": md_file.read_text(encoding="utf-8")[:300] + "...",
            })
    return history

@app.get("/api/summary/{summary_name}")
async def get_summary_content(summary_name: str):
    file_path = Config.OUTPUT_DIR / summary_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Summary not found")
    return {"markdown": file_path.read_text(encoding="utf-8")}

@app.get("/api/download/audio/{filename}")
async def download_audio(filename: str):
    file_path = Config.RECORDINGS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="audio/webm", filename=filename)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web_app:app", host="127.0.0.1", port=8000, reload=False)
