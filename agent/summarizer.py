"""
AI Lecture Summarizer using Google Gemini.
Accepts recorded audio (.webm, .mp3, .wav), uploads directly to Gemini Flash,
and outputs a structured, high-quality markdown summary.
"""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from agent.config import Config

logger = logging.getLogger("agent.summarizer")

SUMMARY_PROMPT_TEMPLATE = """
You are an expert academic assistant and top-tier student note-taker.
Analyze the attached audio recording of a university class/lecture and generate a structured, thorough, yet concise summary.

Language Instructions:
{language_instruction}

Please structure your response in Markdown using the following exact sections:

# 🎓 Class Summary & Notes: [Generate Lecture Topic / Title]
*Date: {date}*

## 📌 Executive Summary
A concise 2-3 paragraph overview of what was covered in this lecture and the primary learning objectives.

## 📚 Key Concepts & Detailed Notes
Break down the main topics chronologically or thematically:
- **[Concept 1]**: Explanation, key formulas, rules, and examples discussed.
- **[Concept 2]**: Explanation, key formulas, rules, and examples discussed.
- *(Include code snippets, definitions, or equations if relevant)*

## ⏰ Important Deadlines, Homework & Announcements
Explicitly list any mention of:
- Upcoming assignments or project submissions (with due dates if stated)
- Midterms, quizzes, or final exam details
- Office hours, changes in schedule, or required readings
*(If none mentioned, explicitly state: "No deadlines or announcements noted.")*

## ❓ Questions & Student Discussions
- **Q**: [Student question]
  - **A**: [Instructor's answer or clarification]
*(If no questions were asked, summarize key discussion points)*

## 📝 Action Items for Next Class
- Specific tasks the student should complete before the next session.

---
### 📝 Verbatim Key Quotes / Highlighted Takeaways
Key statements or emphasized points made by the professor.
"""

class LectureSummarizer:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.GEMINI_API_KEY

    def summarize_audio(self, audio_path: Path, language: str = Config.SUMMARY_LANGUAGE) -> Dict[str, Any]:
        """Summarize lecture audio using Google Gemini API."""
        if not audio_path.exists() or audio_path.stat().st_size == 0:
            return {
                "success": False,
                "error": f"Audio file not found or is empty: {audio_path}",
                "markdown": "### ⚠️ No audio data was recorded.",
            }

        if not self.api_key:
            return {
                "success": False,
                "error": "GEMINI_API_KEY is not configured.",
                "markdown": (
                    "### ⚠️ Gemini API Key Missing\n\n"
                    "To generate AI summaries, please get your free API key from "
                    "[Google AI Studio](https://aistudio.google.com/app/api-keys) and add it to `.env`:\n"
                    "```env\nGEMINI_API_KEY=your_key_here\n```\n\n"
                    f"Your recorded audio is saved at: `{audio_path}`"
                ),
            }

        # Language instructions
        lang_instruction = "Detect the primary language spoken in the lecture (English, Arabic, etc.) and write the summary in that same language."
        if language and language.lower() == "arabic":
            lang_instruction = "The summary MUST be written entirely in clear, professional Arabic (العربية)."
        elif language and language.lower() == "english":
            lang_instruction = "The summary MUST be written in clear, professional English."

        prompt = SUMMARY_PROMPT_TEMPLATE.format(
            language_instruction=lang_instruction,
            date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )

        try:
            return self._call_gemini(audio_path, prompt)
        except Exception as e:
            logger.error(f"Gemini summarization failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "markdown": f"### ⚠️ Error during summarization\n\n`{str(e)}`",
            }

    def _call_gemini(self, audio_path: Path, prompt: str) -> Dict[str, Any]:
        """Upload audio and query Gemini Flash."""
        logger.info(f"Uploading audio file ({audio_path.stat().st_size} bytes) to Gemini API...")

        # We first try google.generativeai
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)

            # Upload audio file
            audio_file = genai.upload_file(path=str(audio_path))
            logger.info(f"File uploaded to Gemini Files API: {audio_file.name}")

            # Wait briefly if processing is needed
            while audio_file.state.name == "PROCESSING":
                time.sleep(2)
                audio_file = genai.get_file(audio_file.name)

            if audio_file.state.name == "FAILED":
                raise RuntimeError("Gemini audio file processing failed.")

            # Generate summary using gemini-1.5-flash or gemini-2.0-flash
            model_name = "gemini-1.5-flash"
            logger.info(f"Generating summary with {model_name}...")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content([audio_file, prompt])

            summary_text = response.text
            return {
                "success": True,
                "markdown": summary_text,
                "model": model_name,
                "audio_file": str(audio_path),
            }

        except ImportError:
            # Try new google-genai SDK
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            uploaded_file = client.files.upload(file=str(audio_path))

            logger.info(f"Generating summary with gemini-2.0-flash...")
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[uploaded_file, prompt],
            )
            return {
                "success": True,
                "markdown": response.text,
                "model": "gemini-2.0-flash",
                "audio_file": str(audio_path),
            }

    def save_summary(self, summary_data: Dict[str, Any], base_filename: str) -> Path:
        """Save generated summary as markdown and metadata JSON."""
        Config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        md_path = Config.OUTPUT_DIR / f"{base_filename}_summary.md"
        json_path = Config.OUTPUT_DIR / f"{base_filename}_metadata.json"

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(summary_data.get("markdown", ""))

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved summary to {md_path}")
        return md_path
