from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse
import hmac, hashlib, json, base64
from typing import Optional

from .config import settings
from .github_api import GitHubService
from .review import ReviewEngine

app = FastAPI(title="AI Code Review Bot")

gh = GitHubService()
engine = ReviewEngine()

def verify_signature(body: bytes, signature_header: Optional[str]) -> bool:
    """
    Verify GitHub's X-Hub-Signature-256.
    """
    if not settings.github_webhook_secret:
        # If no secret is set, accept (useful for local dev). For production, require it.
        return True

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    digest = hmac.new(
        settings.github_webhook_secret.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(f"sha256={digest}", signature_header)


@app.get("/")
def health():
    return {"status": "AI Code Review Bot is running"}


@app.post("/webhook")
async def webhook(
    request: Request,
):
    raw = await request.body()
    print("Webhook Recieved")
    x_hub_signature_256 = request.headers.get("X-Hub-Signature-256")
    if not verify_signature(raw, x_hub_signature_256):
        print("sign")
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = await request.json()
    except Exception:
        print("Exception")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    x_github_event = request.headers.get("X-GitHub-Event")

    if x_github_event != "pull_request":
        return JSONResponse({"status": "ignored", "reason": "not a pull_request event"})

    action = payload.get("action")
    if action not in ("opened", "synchronize", "ready_for_review", "edited", "reopened"):
        return JSONResponse({"status": "ignored", "reason": f"action {action} not handled"})

    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {})
    if not pr or not repo:
        raise HTTPException(status_code=400, detail="Missing PR or repository data")

    pr_number = pr["number"]
    owner = repo["owner"]["login"]
    name = repo["name"]

    if pr.get("draft"):
        return JSONResponse({"status": "skipped", "reason": "draft PR"})

    try:
        diff_text = gh.get_pr_diff(owner, name, pr_number)
    except Exception as e:
        gh.post_pr_comment(owner, name, pr_number, f"❌ Failed to fetch diff: `{e}`")
        raise

    if not diff_text.strip():
        gh.post_pr_comment(owner, name, pr_number, "ℹ️ No diff content found for this PR.")
        return {"status": "no_diff"}

    try:
        review = engine.review_diff(diff_text)
    except Exception as e:
        gh.post_pr_comment(owner, name, pr_number, f"❌ LLM review failed: `{e}`")
        raise

    comment = engine.format_review_comment(review)
    gh.post_pr_comment(owner, name, pr_number, comment)

    return {"status": "review_posted", "pr": pr_number}