from fastapi import FastAPI, Request
import hmac
import hashlib
import os
from dotenv import load_dotenv

app = FastAPI()

load_dotenv()
GITHUB_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")

@app.post("/webhook")
async def github_webhook(request: Request):
    # Verify GitHub signature for security
    body = await request.body()
    print("✅ Webhook received")
    signature = request.headers.get("X-Hub-Signature-256")
    if not is_valid_signature(body, signature):
        return {"status": "invalid signature"}

    payload = await request.json()
    event = request.headers.get("X-GitHub-Event")

    if event == "pull_request":
        action = payload.get("action")
        pr_title = payload["pull_request"]["title"]
        pr_url = payload["pull_request"]["html_url"]

        print(f"PR Event: {action} - {pr_title} ({pr_url})")

    return {"status": "received"}

@app.get("/")
def home():
    return {"status": "AI Code Review Bot is running"}

def is_valid_signature(payload_body, signature_header):
    if signature_header is None:
        return False
    mac = hmac.new(
        GITHUB_SECRET.encode(),
        msg=payload_body,
        digestmod=hashlib.sha256
    )
    expected = f"sha256={mac.hexdigest()}"
    return hmac.compare_digest(expected, signature_header)
