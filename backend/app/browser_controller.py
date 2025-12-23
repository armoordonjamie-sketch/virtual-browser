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
        self.listeners = set()
        self._cdp_client = None

    async def add_listener(self):
        queue = asyncio.Queue(maxsize=1)
        self.listeners.add(queue)
        return queue

    async def remove_listener(self, queue):
        self.listeners.discard(queue)

    async def start(self, headless: bool = True):
        logger.info(f"Starting browser (headless={headless})...")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu'] # disable-gpu might help stability
        )
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )
        self.page = await self.context.new_page()
        
        await self.page.goto("https://chatgpt.com/chat")
        
        self._cdp_client = await self.context.new_cdp_session(self.page)
        self._cdp_client.on("Page.screencastFrame", self._on_screencast_frame)
        
        # Optimize for performance: slightly lower JPEG quality, but higher max buffer?
        # Actually CDP caps us around 30fps usually. 
        # lowering quality to 70 might help transfer speed.
        await self._cdp_client.send(
            "Page.startScreencast", 
            {"format": "jpeg", "quality": 70, "maxWidth": 1920, "maxHeight": 1080, "everyNthFrame": 1}
        )
        logger.info("Browser started and screencast active.")

    async def _on_screencast_frame(self, params):
        data = params.get("data")
        session_id = params.get("sessionId")
        
        # data is base64 encoded string
        if data:
            self.last_frame = base64.b64decode(data)
            # Broadcast to all listeners
            for queue in list(self.listeners):
                if queue.full():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                try:
                    queue.put_nowait(self.last_frame)
                except asyncio.QueueFull:
                    pass

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
        
        elif action == "dblclick":
            x, y = params.get("x"), params.get("y")
            if x is not None and y is not None:
                await self.page.mouse.dblclick(x, y)
        
        elif action == "rightclick":
            x, y = params.get("x"), params.get("y")
            if x is not None and y is not None:
                await self.page.mouse.click(x, y, button="right")
        
        elif action == "scroll":
            x, y = params.get("x"), params.get("y")
            deltaX = params.get("deltaX", 0)
            deltaY = params.get("deltaY", 0)
            if x is not None and y is not None:
                await self.page.mouse.move(x, y)
                await self.page.mouse.wheel(deltaX, deltaY)
        
        elif action == "keydown":
            key = params.get("key")
            if key:
                # Handle modifier combinations
                modifiers = []
                if params.get("ctrlKey"):
                    modifiers.append("Control")
                if params.get("shiftKey"):
                    modifiers.append("Shift")
                if params.get("altKey"):
                    modifiers.append("Alt")
                if params.get("metaKey"):
                    modifiers.append("Meta")
                
                if modifiers and key not in ["Control", "Shift", "Alt", "Meta"]:
                    # Press with modifiers
                    combo = "+".join(modifiers + [key])
                    await self.page.keyboard.press(combo)
                else:
                    await self.page.keyboard.press(key)
        
        elif action == "keypress":
            key = params.get("key")
            if key:
                await self.page.keyboard.press(key)
        
        elif action == "type":
            text = params.get("text")
            if text:
                await self.page.keyboard.type(text)
        
        elif action == "back":
            try:
                await self.page.go_back()
            except Exception as e:
                logger.error(f"Back navigation failed: {e}")
        
        elif action == "forward":
            try:
                await self.page.go_forward()
            except Exception as e:
                logger.error(f"Forward navigation failed: {e}")
        
        elif action == "reload":
            try:
                await self.page.reload()
            except Exception as e:
                logger.error(f"Reload failed: {e}")
        
        elif action == "resize":
             width = params.get("width")
             height = params.get("height")
             if width and height:
                 await self.page.set_viewport_size({"width": int(width), "height": int(height)})
        
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
