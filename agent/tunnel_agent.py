#!/usr/bin/env python3
import asyncio, hashlib, json
import aiohttp, websockets
from config import load

CENTRAL_WS = "ws://127.0.0.1:5090/ws/tunnel/"
LOCAL_API = "http://127.0.0.1:8000"  # your local Django/Flask server

async def handle_request(frame, ws):
    if frame.get("action") != "proxy_request":
        return
    req_id   = frame["id"]
    method   = frame["method"]
    path     = frame["path"]
    headers  = frame.get("headers", {})
    body     = frame.get("body", "")

    url = f"{LOCAL_API}/{path.lstrip('/')}"
    async with aiohttp.ClientSession() as sess:
        try:
            async with sess.request(method, url, headers=headers, data=body) as resp:
                text = await resp.text()
                out = {
                    "action": "http_response",
                    "id":      req_id,
                    "status":  resp.status,
                    "headers": dict(resp.headers),
                    "body":    text
                }
        except Exception as e:
            out = {
                "action": "http_response",
                "id":      req_id,
                "status":  500,
                "headers": {},
                "body":    f"Error: {e}"
            }
    await ws.send(json.dumps(out))

async def run():
    cfg = load()
    if not cfg.get("house_id"):
        print("Please run `agent/register.py` first to register.")
        return

    hid, sk = cfg["house_id"], cfg["secret_key"]
    auth_hash = hashlib.sha256((hid + sk).encode()).hexdigest()

    while True:
        try:
            async with websockets.connect(CENTRAL_WS) as ws:
                # Authenticate
                await ws.send(json.dumps({
                    "action":    "authenticate",
                    "house_id":  hid,
                    "auth_hash": auth_hash
                }))
                print("🔌 Tunnel connected as", hid)

                async for msg in ws:
                    frame = json.loads(msg)
                    await handle_request(frame, ws)

        except Exception as exc:
            print("Tunnel error:", exc, "→ retrying in 5s…")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(run())
