
import os
from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.auth import verify_credentials
from app.browser_controller import browser_manager
from app.streaming import rtc_manager
from app.utils import setup_logger

setup_logger()

app = FastAPI(title="Virtual Browser Streaming")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup templates
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

class CallbackModel(BaseModel):
    sdp: str
    type: str

@app.on_event("startup")
async def startup_event():
    # We don't auto-start browser to save resources, wait for user
    pass

@app.on_event("shutdown")
async def shutdown_event():
    await browser_manager.stop()
    await rtc_manager.shutdown()

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request, username: str = Depends(verify_credentials)):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/start")
async def start_browser(username: str = Depends(verify_credentials)):
    if not browser_manager.browser:
        await browser_manager.start(headless=True)
    return {"status": "started"}

@app.post("/stop")
async def stop_browser(username: str = Depends(verify_credentials)):
    await browser_manager.stop()
    return {"status": "stopped"}

@app.post("/offer")
async def offer(params: CallbackModel, username: str = Depends(verify_credentials)):
    answer = await rtc_manager.handle_offer(params.sdp, params.type)
    return JSONResponse(answer)

@app.post("/navigate")
async def navigate(request: Request, username: str = Depends(verify_credentials)):
    data = await request.json()
    url = data.get("url")
    if url:
        await browser_manager.handle_input("navigate", {"url": url})
    return {"status": "navigated"}
