import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure UTF-8 output encoding on Windows consoles to support Arabic paths & summaries
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Load environment variables from .env file
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class Config:
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    STUDENT_NAME: str = os.getenv("STUDENT_NAME", "Student").strip()
    SUMMARY_LANGUAGE: str = os.getenv("SUMMARY_LANGUAGE", "Auto").strip()
    HEADLESS: bool = os.getenv("HEADLESS", "False").lower() in ("true", "1", "yes")

    # Directory configurations
    BASE_DIR: Path = BASE_DIR
    RECORDINGS_DIR: Path = BASE_DIR / os.getenv("RECORDINGS_DIR", "recordings")
    OUTPUT_DIR: Path = BASE_DIR / os.getenv("OUTPUT_DIR", "output")
    USER_DATA_DIR: Path = BASE_DIR / os.getenv("USER_DATA_DIR", "browser_profile")

    @classmethod
    def ensure_dirs(cls):
        """Ensure all required runtime directories exist."""
        cls.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Automatically ensure directories on import
Config.ensure_dirs()
