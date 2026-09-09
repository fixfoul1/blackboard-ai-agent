"""
Browser engine management using Playwright with persistent profiles,
stealth settings, and auto-granted WebRTC permissions.
"""

import logging
from pathlib import Path
from typing import Optional
from playwright.async_api import async_playwright, BrowserContext, Page, Playwright
from agent.config import Config

logger = logging.getLogger("agent.browser")

# Chromium launch flags to bypass media prompts and enable background autoplay
CHROMIUM_ARGS = [
    "--use-fake-ui-for-media-stream",       # Auto-accept mic/cam permission prompts
    "--use-fake-device-for-media-stream",   # Provide virtual silent mic/cam (prevents real mic broadcast)
    "--autoplay-policy=no-user-gesture-required", # Allow audio to play without initial user interaction
    "--disable-blink-features=AutomationControlled", # Reduce automation detection flags
    "--no-sandbox",
    "--disable-setuid-sandbox",
]

class BrowserManager:
    def __init__(
        self,
        headless: bool = Config.HEADLESS,
        user_data_dir: Path = Config.USER_DATA_DIR,
        record_video_dir: Optional[Path] = None,
    ):
        self.headless = headless
        self.user_data_dir = user_data_dir
        self.record_video_dir = record_video_dir
        self.playwright: Optional[Playwright] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def start(self) -> Page:
        """Launch persistent Chromium context and return the main active page."""
        logger.info(f"Launching Chromium (Headless: {self.headless}, Profile: {self.user_data_dir})")
        self.playwright = await async_playwright().start()

        viewport = {"width": 1280, "height": 800}

        # Setup persistent context so university SSO logins and cookies persist
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.user_data_dir),
            headless=self.headless,
            args=CHROMIUM_ARGS,
            permissions=["microphone", "camera"],
            viewport=viewport,
            record_video_dir=str(self.record_video_dir) if self.record_video_dir else None,
            record_video_size=viewport if self.record_video_dir else None,
            ignore_default_args=["--mute-audio"], # Ensure browser tab audio is NOT muted
        )

        # Get or create page
        pages = self.context.pages
        if pages:
            self.page = pages[0]
        else:
            self.page = await self.context.new_page()

        logger.info("Chromium context launched successfully.")
        return self.page

    async def close(self):
        """Close context and shutdown playwright."""
        try:
            if self.context:
                await self.context.close()
                self.context = None
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
            logger.info("Browser context closed cleanly.")
        except Exception as e:
            logger.warning(f"Error during browser cleanup: {e}")
