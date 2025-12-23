
# Virtual Browser Streaming Service

A remote browser isolation system built with Python, FastAPI, Playwright, and WebRTC.

## Overview
This project allows you to run a Chromium browser instance on a remote server (or container) and stream its visual output to a client browser via WebRTC. User inputs (mouse/keyboard) are sent back to the server to control the browser in real-time.

**Architecture:**
- **Backend**: FastAPI (Python) handles API requests and WebRTC signaling.
- **Browser Automation**: Playwright controls a headless Chromium instance.
- **Capture**: Uses Chrome DevTools Protocol (CDP) `Page.startScreencast`.
- **Streaming**: `aiortc` encodes frames and sends them over a WebRTC PeerConnection.

## Prerequisites
- Python 3.9+
- Linux (for production) or Windows/Mac (local dev)
- Chrome/Chromium installed (handled by Playwright)

## Setup (Local)

1. **Clone the repo**
   ```bash
   git clone https://github.com/armoordonjamie-sketch/virtual-browser.git
   cd virtual-browser
   ```

2. **Create Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r backend/requirements.txt
   playwright install chromium
   ```

4. **Configuration**
   Copy `.env.example` to `.env` in `backend/` and set your secrets.
   ```bash
   cp backend/.env.example backend/.env
   ```

## Running Locally

1. **Start the Server**
   ```bash
   cd backend
   uvicorn app.main:app --reload
   ```

2. **Access the App**
   Open `http://localhost:8000`.
   - Click **Start Browser**.
   - Click **Connect Stream**.
   - You should see the remote browser. Type a URL and click **Go**.

## Deploy on Linux VPS

1. **Prepare Server**
   - SSH into your server (Ubuntu 20.04/22.04 recommended).
   - Install Python, pip, and system dependencies:
     ```bash
     sudo apt update && sudo apt install -y python3-pip python3-venv libgl1-mesa-glx libglib2.0-0 nginx git
     ```

2. **Install Application**
   - Clone repo and install deps as above.
   - **Important**: Playwright needs dependencies.
     ```bash
     playwright install-deps chromium
     playwright install chromium
     ```

3. **Systemd Service**
   Create `/etc/systemd/system/browser-stream.service`:
   ```ini
   [Unit]
   Description=Virtual Browser Service
   After=network.target

   [Service]
   User=root
   WorkingDirectory=/path/to/virtual-browser/backend
   ExecStart=/path/to/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```
   Start it: `sudo systemctl enable --now browser-stream`

4. **Nginx Reverse Proxy**
   Create `/etc/nginx/sites-available/browser`:
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_set_header Host $host;
       }
   }
   ```
   Enable it: `ln -s /etc/nginx/sites-available/browser /etc/nginx/sites-enabled/`
   Test & Reload: `nginx -t && systemctl reload nginx`

5. **SSL (Certbot)**
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d your-domain.com
   ```

## Git Usage
Initialize and push:
```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/armoordonjamie-sketch/virtual-browser
git push -u origin main
```
