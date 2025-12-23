
import asyncio
import base64
import logging
from typing import Optional, Callable, Awaitable
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

logger = logging.getLogger(__name__)

class BrowserManager:
    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.last_frame: Optional[bytes] = None
        self.frame_callback: Optional[Callable[[bytes], Awaitable[None]]] = None
        self._cdp_client = None

    async def start(self, headless: bool = True):
        logger.info(f"Starting browser (headless={headless})...")
        self.playwright = await async_playwright().start()
        # Launch Chromium. Add args for container/linux env if needed
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 720}
        )
        self.page = await self.context.new_page()
        
        # Go to a default page
        await self.page.goto("https://www.google.com")
        
        # Start CDP session for screencast
        self._cdp_client = await self.context.new_cdp_session(self.page)
        self._cdp_client.on("Page.screencastFrame", self._on_screencast_frame)
        
        # Start screencast
        await self._cdp_client.send(
            "Page.startScreencast", 
            {"format": "jpeg", "quality": 80, "maxWidth": 1280, "maxHeight": 720}
        )
        logger.info("Browser started and screencast active.")

    async def _on_screencast_frame(self, params):
        data = params.get("data")
        session_id = params.get("sessionId")
        
        # data is base64 encoded string
        if data:
            self.last_frame = base64.b64decode(data)
            if self.frame_callback:
                asyncio.create_task(self.frame_callback(self.last_frame))

        # Acknowledge the frame to keep the stream coming
        try:
            await self._cdp_client.send("Page.screencastFrameAck", {"sessionId": session_id})
        except Exception as e:
            logger.error(f"Error checking frame ack: {e}")

    async def stop(self):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("Browser stopped.")

    async def handle_input(self, action: str, params: dict):
        if not self.page:
            return

        if action == "mousemove":
            x, y = params.get("x"), params.get("y")
            if x is not None and y is not None:
                await self.page.mouse.move(x, y)
        
        elif action == "click":
            x, y = params.get("x"), params.get("y")
            if x is not None and y is not None:
                await self.page.mouse.click(x, y)
        
        elif action == "keypress":
            key = params.get("key")
            if key:
                await self.page.keyboard.press(key)
        
        elif action == "type":
            text = params.get("text")
            if text:
                await self.page.keyboard.type(text)
        
        elif action == "resize":
             width = params.get("width")
             height = params.get("height")
             if width and height:
                 await self.page.set_viewport_size({"width": int(width), "height": int(height)})
                 # Restart screencast with new dims might be needed, or just update viewport
                 # CDP spec says startScreencast might need re-triggering for prop updates?
                 # Actually viewport change usually triggers new frames naturally.
        
        elif action == "navigate":
            url = params.get("url")
            if url:
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url
                try:
                    await self.page.goto(url)
                except Exception as e:
                    logger.error(f"Navigation failed: {e}")

# Singleton instance
browser_manager = BrowserManager()
