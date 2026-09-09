# 🎓 Blackboard AI Class Attender, Recorder & Summarizer Agent

An autonomous AI agent that attends your Blackboard Collaborate classes, records high-fidelity audio and presentation video, transcribes the lecture, and generates structured AI summaries using Google Gemini Flash.

---

## ✨ Features

- **🚀 Autonomous Attendance**: Joins Blackboard Collaborate sessions using direct guest links or university LMS portals.
- **🛡️ Silent & Stealthy**: Automatically mutes the microphone and camera upon room entry, and bypasses audio/video test dialogs and tutorial popups.
- **🎙️ Clean Audio & Video Recording**: In-page WebRTC and Web Audio capture streams crystal-clear audio of the professor and participants, while tab recording captures slides and screen sharing.
- **🧠 Gemini AI Summaries**: Leverages Google Gemini Flash to generate comprehensive lecture summaries:
  - 📌 **Executive Summary** (Quick recap)
  - 📚 **Key Concepts & Detailed Notes** (Theories, formulas, code, definitions)
  - ⏰ **Deadlines, Homework & Announcements** (Never miss a submission or exam notice)
  - ❓ **Questions & Answers** (Student questions and instructor explanations)
  - 📝 **Action Items** (Preparation for the next lecture)
- **🌐 Dual Interface**:
  - **Modern Web Dashboard**: Intuitive web page with live timer, start/stop buttons, history viewer, and formatted markdown rendering.
  - **Interactive CLI**: Fast command-line interface with color-coded live progress and terminal markdown reader.
- **🔐 Persistent Login Profile**: Supports university Single Sign-On (SSO) and Two-Factor Authentication (2FA) so you only need to sign in once.

---

## 🛠️ Quick Setup

### 1. Configure Your Environment

Copy the example environment file and add your Gemini API Key:

```bash
cp .env.example .env
```

Open `.env` and insert your free key from [Google AI Studio](https://aistudio.google.com/app/api-keys):
```env
GEMINI_API_KEY=your_gemini_api_key_here
STUDENT_NAME=Your Name
SUMMARY_LANGUAGE=Auto
HEADLESS=False
```

### 2. Install Playwright Chromium Browser

Run once to download the Chromium browser binary:
```bash
python -m playwright install chromium
```

---

## 🖥️ Usage

### Option 1: Modern Web Dashboard (Recommended)

Launch the dashboard:
```bash
python web_app.py
```
Open your browser and navigate to: **`http://localhost:8000`**
1. Paste your Blackboard Collaborate session URL.
2. Enter your student display name.
3. Click **"Join & Start Recording"**.
4. When class concludes, click **"Leave & Generate Summary"** to view and copy your AI-generated notes.

---

### Option 2: Command Line Interface (CLI)

#### 1. Join and Record a Live Session
```bash
python cli.py join --url "https://us.bbcollab.com/collab/ui/guest/meeting/..." --name "Alex"
```
- Set an automatic time limit (e.g. 60 minutes):
  ```bash
  python cli.py join --url "https://..." --duration 60
  ```
- Run in background (headless mode):
  ```bash
  python cli.py join --url "https://..." --headless
  ```
- Press **`Ctrl+C`** at any time to leave early and generate the summary immediately.

#### 2. Summarize an Existing Audio Recording
```bash
python cli.py summarize --audio "recordings/class_20260909_170000.webm"
```

#### 3. Log into University Blackboard Portal (One-time SSO / 2FA setup)
If your university requires logging in via Blackboard Learn instead of guest links:
```bash
python cli.py login --url "https://youruniversity.blackboard.com"
```
Log in manually in the browser window that opens. All authentication cookies and session tokens will be permanently saved in `browser_profile/` for future autonomous joins!

---

## 📁 Directory Structure

```
├── agent/
│   ├── blackboard.py    # Blackboard Collaborate UI automation & dialog dismisser
│   ├── browser.py       # Playwright browser manager & persistent profile
│   ├── config.py        # Settings and environment loader
│   ├── orchestrator.py  # End-to-end workflow coordinator
│   ├── recorder.py      # In-browser WebRTC / HTML5 audio capture engine
│   └── summarizer.py    # Google Gemini audio transcription & summarizer
├── templates/
│   └── index.html       # Web dashboard frontend
├── recordings/          # Saved audio (.webm) and video recordings
├── output/              # Generated markdown summaries (.md) and JSON metadata
├── browser_profile/     # Persistent browser session for university SSO
├── cli.py               # Command line interface
├── web_app.py           # FastAPI local web dashboard
├── requirements.txt     # Python dependencies
└── .env                 # API keys & configuration
```
