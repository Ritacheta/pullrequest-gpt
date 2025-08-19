import json
from typing import Dict, Any

from backend.config import settings
import requests

# Using OpenAI API directly (no heavy orchestration deps).
# If you prefer LangChain, you can swap this out later.

class ReviewEngine:
    def __init__(self):
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not set")

        # Basic options
        self.model = settings.openai_model or "gpt-4o-mini"
        self.api_base = settings.openai_base or "https://api.openai.com/v1"

        # Load prompts
        with open(settings.prompts_dir / "review_prompt.txt", "r", encoding="utf-8") as f:
            self.review_template = f.read()
        with open(settings.prompts_dir / "refactor_prompt.txt", "r", encoding="utf-8") as f:
            self.refactor_template = f.read()

    def _chat(self, messages):
        url = f"{self.api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": messages,
        }
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"OpenAI HTTP {r.status_code}: {r.text}")
        data = r.json()
        return data["choices"][0]["message"]["content"]

    def review_diff(self, diff_text: str) -> Dict[str, Any]:
        """
        Returns a dict with sections:
        code_quality, security_issues, performance_issues, best_practices, suggested_changes
        """
        system = "You are a senior staff engineer performing rigorous code reviews."
        user = self.review_template.replace("{diff}", diff_text[:200000])  # cap to avoid token blowups
        content = self._chat([{"role": "system", "content": system}, {"role": "user", "content": user}])

        # Force JSON parsing; if the model slips, try to recover
        try:
            review = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON block
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1 and end > start:
                review = json.loads(content[start : end + 1])
            else:
                raise RuntimeError("LLM did not return valid JSON")
        return review

    def format_review_comment(self, review: Dict[str, Any]) -> str:
        # Pretty print JSON and a short summary
        safe = {
            "code_quality": review.get("code_quality", []),
            "security_issues": review.get("security_issues", []),
            "performance_issues": review.get("performance_issues", []),
            "best_practices": review.get("best_practices", []),
            "suggested_changes": review.get("suggested_changes", []),
        }

        summary_points = []
        if safe["security_issues"]:
            summary_points.append(f"Security: {len(safe['security_issues'])} issue(s)")
        if safe["performance_issues"]:
            summary_points.append(f"Performance: {len(safe['performance_issues'])} issue(s)")
        if safe["best_practices"]:
            summary_points.append(f"Best Practices: {len(safe['best_practices'])} finding(s)")
        if safe["code_quality"]:
            summary_points.append(f"Code Quality: {len(safe['code_quality'])} suggestion(s)")
        if safe["suggested_changes"]:
            summary_points.append(f"Refactors: {len(safe['suggested_changes'])}")

        summary_line = " | ".join(summary_points) if summary_points else "No major issues found ✅"

        return (
            f"## 🤖 AI Code Review\n"
            f"**Summary:** {summary_line}\n\n"
            f"<details>\n<summary>Structured Findings (JSON)</summary>\n\n"
            f"```json\n{json.dumps(safe, indent=2)}\n```\n"
            f"</details>\n\n"
            f"_Model: {self.model}_"
        )
