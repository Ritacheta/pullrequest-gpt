import os
import requests

from backend.config import settings

class GitHubService:
    BASE_URL = "https://api.github.com"

    def __init__(self):
        if not settings.github_token:
            raise ValueError("GITHUB_TOKEN is not set")
        self.headers_json = {
            "Authorization": f"token {settings.github_token}",
            "Accept": "application/vnd.github+json",
        }
        self.headers_diff = {
            "Authorization": f"token {settings.github_token}",
            "Accept": "application/vnd.github.v3.diff",
        }

    def get_pr_diff(self, owner: str, repo: str, pr_number: int) -> str:
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}"
        r = requests.get(url, headers=self.headers_diff, timeout=30)
        if r.status_code == 404:
            raise FileNotFoundError(
                f"PR #{pr_number} not found in {owner}/{repo}. "
                "Ensure the token user has access and the token has 'repo' scope."
            )
        if r.status_code == 401:
            raise PermissionError("Unauthorized. Check GITHUB_TOKEN and scopes.")
        if r.status_code != 200:
            raise RuntimeError(f"Failed to fetch diff: {r.status_code} - {r.text}")
        return r.text

    def post_pr_comment(self, owner: str, repo: str, pr_number: int, body: str):
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues/{pr_number}/comments"
        payload = {"body": body}
        r = requests.post(url, headers=self.headers_json, json=payload, timeout=30)
        if r.status_code == 401:
            raise PermissionError("Unauthorized")
        if r.status_code == 404:
            raise FileNotFoundError("Cannot post comment. Check repo/PR permissions.")
        if r.status_code not in (200, 201):
            raise RuntimeError(f"Failed to post comment: {r.status_code} - {r.text}")
        return r.json()
