
import asyncio
import logging
import io
import json
import av
from aiortc import VideoStreamTrack, RTCPeerConnection, RTCSessionDescription
from app.browser_controller import browser_manager

logger = logging.getLogger(__name__)

class BrowserVideoTrack(VideoStreamTrack):
    """
    A video stream track that transforms frames from the browser screencast
    into WebRTC video frames.
    """
    def __init__(self):
        super().__init__()
        self.queue = None
        self._ended = False
        self._setup_lock = asyncio.Lock()

    async def _ensure_queue(self):
        async with self._setup_lock:
            if self.queue is None and not self._ended:
                self.queue = await browser_manager.add_listener()

    async def recv(self):
        if self._ended:
            return None
        
        if self.queue is None:
            await self._ensure_queue()
            
        pts, time_base = await self.next_timestamp()
        
        try:
            # Wait for next frame from browser
            if self.queue:
                jpeg_bytes = await self.queue.get()
                
                # Decode JPEG
                container = av.open(io.BytesIO(jpeg_bytes))
                try:
                    frames = list(container.decode(video=0))
                    if frames:
                        frame = frames[0]
                        frame.pts = pts
                        frame.time_base = time_base
                        return frame
                finally:
                    container.close()
                
        except Exception as e:
            logger.error(f"Frame processing error: {e}")
            pass
            
        return None

    def on_ended(self):
        self._ended = True
        if self.queue:
            asyncio.create_task(browser_manager.remove_listener(self.queue))
            self.queue = None

class RTCManager:
    def __init__(self):
        self.pcs = set()

    async def handle_offer(self, sdp: str, type: str):
        pc = RTCPeerConnection()
        self.pcs.add(pc)
        
        video_sender = pc.addTrack(BrowserVideoTrack())

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info(f"Connection state is {pc.connectionState}")
            if pc.connectionState in ["failed", "closed"]:
                try:
                    await pc.close()
                except Exception:
                    pass
                self.pcs.discard(pc)

        @pc.on("datachannel")
        def on_datachannel(channel):
            @channel.on("message")
            async def on_message(message):
                try:
                    data = json.loads(message)
                    action = data.get("action")
                    if action:
                        await browser_manager.handle_input(action, data)
                except Exception as e:
                    logger.error(f"Data channel message error: {e}")

        # Set remote description
        offer = RTCSessionDescription(sdp=sdp, type=type)
        await pc.setRemoteDescription(offer)
        
        # Create answer
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        
        return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}

    async def shutdown(self):
        coros = [pc.close() for pc in self.pcs]
        await asyncio.gather(*coros)
        self.pcs.clear()

rtc_manager = RTCManager()
