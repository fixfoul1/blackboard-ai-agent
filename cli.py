"""
Command Line Interface (CLI) for Blackboard AI Class Agent.
Supports interactive joining, recording, standalone summarization,
and one-time login for persistent university SSO sessions.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from agent.config import Config
from agent.orchestrator import SessionOrchestrator
from agent.summarizer import LectureSummarizer
from agent.browser import BrowserManager

console = Console()

def print_banner():
    console.print(
        Panel(
            "[bold cyan]🎓 Blackboard AI Class Attender & Summarizer Agent[/bold cyan]\n"
            "[dim]Autonomous class attendance, high-fidelity audio/video recording, and Gemini summaries[/dim]",
            border_style="cyan",
        )
    )

async def cmd_join(args):
    print_banner()
    console.print(f"[bold green]▶ Target URL:[/bold green] {args.url}")
    console.print(f"[bold green]▶ Student Name:[/bold green] {args.name or Config.STUDENT_NAME}")
    if args.duration:
        console.print(f"[bold green]▶ Duration Limit:[/bold green] {args.duration} minutes")
    console.print("[dim]Press Ctrl+C at any time to stop recording and generate the summary immediately.[/dim]\n")

    orchestrator = SessionOrchestrator(
        student_name=args.name or Config.STUDENT_NAME,
        headless=args.headless,
        record_video=not args.no_video,
    )

    def on_status(msg: str):
        console.print(f"[bold yellow]●[/bold yellow] {msg}")

    # Handle Ctrl+C gracefully
    loop = asyncio.get_event_loop()

    try:
        results = await orchestrator.run(
            session_url=args.url,
            duration_minutes=args.duration,
            status_callback=on_status,
        )

        console.print("\n[bold green]✔ Recording & Summarization Complete![/bold green]")
        console.print(f"📁 [bold]Audio File:[/bold] {results['audio_file']}")
        console.print(f"📄 [bold]Summary File:[/bold] {results['summary_file']}\n")

        # Display rendered summary in terminal
        console.print(Panel(Markdown(results["summary_markdown"]), title="🎓 Lecture Summary", border_style="green"))

    except KeyboardInterrupt:
        console.print("\n[bold red]Interrupted by user. Stopping session and generating summary...[/bold red]")
        orchestrator.stop()

async def cmd_summarize(args):
    print_banner()
    audio_path = Path(args.audio)
    if not audio_path.exists():
        console.print(f"[bold red]Error: Audio file not found:[/bold red] {audio_path}")
        return

    console.print(f"[bold blue]Summarizing audio recording:[/bold blue] {audio_path}")
    summarizer = LectureSummarizer()

    with console.status("[bold green]Uploading to Gemini & analyzing lecture audio..."):
        result = summarizer.summarize_audio(audio_path)

    base_name = audio_path.stem
    summary_path = summarizer.save_summary(result, base_name)

    console.print(f"\n[bold green]✔ Summary generated and saved to:[/bold green] {summary_path}\n")
    console.print(Panel(Markdown(result.get("markdown", "")), title="🎓 Lecture Summary", border_style="green"))

async def cmd_login(args):
    print_banner()
    console.print(
        "[bold yellow]Opening browser for University Blackboard Login...[/bold yellow]\n"
        "Log in with your university credentials and complete any 2FA/SSO.\n"
        "Your session cookies will be saved in the persistent profile folder.\n"
        "[dim]Close the browser window when finished logging in.[/dim]\n"
    )
    url = args.url or "https://blackboard.com"
    browser_manager = BrowserManager(headless=False)
    page = await browser_manager.start()
    await page.goto(url)

    # Keep alive until user closes the browser
    try:
        while True:
            if not browser_manager.context or len(browser_manager.context.pages) == 0:
                break
            await asyncio.sleep(1)
    except Exception:
        pass
    finally:
        await browser_manager.close()
        console.print("[bold green]✔ Session profile saved successfully![/bold green]")

def main():
    parser = argparse.ArgumentParser(description="Blackboard AI Class Attender & Summarizer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Join command
    join_parser = subparsers.add_parser("join", help="Join a Blackboard Collaborate session, record, and summarize")
    join_parser.add_argument("--url", "-u", required=True, help="Blackboard Collaborate session or guest link URL")
    join_parser.add_argument("--name", "-n", default=None, help="Display name when joining")
    join_parser.add_argument("--duration", "-d", type=int, default=None, help="Auto-leave duration limit in minutes")
    join_parser.add_argument("--headless", action="store_true", default=Config.HEADLESS, help="Run browser in background (headless)")
    join_parser.add_argument("--no-video", action="store_true", help="Disable video recording (audio only)")

    # Summarize command
    sum_parser = subparsers.add_parser("summarize", help="Summarize an existing audio recording")
    sum_parser.add_argument("--audio", "-a", required=True, help="Path to audio file (.webm, .mp3, .wav)")

    # Login command
    login_parser = subparsers.add_parser("login", help="Open browser to log in to university LMS and save session")
    login_parser.add_argument("--url", "-u", default=None, help="University Blackboard login portal URL")

    args = parser.parse_args()

    if args.command == "join":
        asyncio.run(cmd_join(args))
    elif args.command == "summarize":
        asyncio.run(cmd_summarize(args))
    elif args.command == "login":
        asyncio.run(cmd_login(args))

if __name__ == "__main__":
    main()
