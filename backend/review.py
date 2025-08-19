# import json
# from typing import Dict, Any

# from backend.config import settings
# import requests

# # Using OpenAI API directly (no heavy orchestration deps).
# # If you prefer LangChain, you can swap this out later.

# class ReviewEngine:
#     def __init__(self):
#         if not settings.openai_api_key:
#             raise ValueError("OPENAI_API_KEY is not set")

#         # Basic options
#         self.model = settings.openai_model or "gpt-4o-mini"
#         self.api_base = settings.openai_base or "https://api.openai.com/v1"

#         # Load prompts
#         with open(settings.prompts_dir / "review_prompt.txt", "r", encoding="utf-8") as f:
#             self.review_template = f.read()
#         with open(settings.prompts_dir / "refactor_prompt.txt", "r", encoding="utf-8") as f:
#             self.refactor_template = f.read()

#     def _chat(self, messages):
#         url = f"{self.api_base}/chat/completions"
#         headers = {
#             "Authorization": f"Bearer {settings.openai_api_key}",
#             "Content-Type": "application/json",
#         }
#         payload = {
#             "model": self.model,
#             "temperature": 0,
#             "messages": messages,
#         }
#         print("Message: ", messages)
#         r = requests.post(url, headers=headers, json=payload, timeout=60)
#         if r.status_code != 200:
#             raise RuntimeError(f"OpenAI HTTP {r.status_code}: {r.text}")
#         data = r.json()
#         return data["choices"][0]["message"]["content"]

#     def review_diff(self, diff_text: str) -> Dict[str, Any]:
#         """
#         Returns a dict with sections:
#         code_quality, security_issues, performance_issues, best_practices, suggested_changes
#         """
#         system = "You are a senior staff engineer performing rigorous code reviews."
#         user = self.review_template.replace("{diff}", diff_text[:200000])  # cap to avoid token blowups
#         content = self._chat([{"role": "system", "content": system}, {"role": "user", "content": user}])

#         # Force JSON parsing; if the model slips, try to recover
#         try:
#             review = json.loads(content)
#         except json.JSONDecodeError:
#             # Try to extract JSON block
#             start = content.find("{")
#             end = content.rfind("}")
#             if start != -1 and end != -1 and end > start:
#                 review = json.loads(content[start : end + 1])
#             else:
#                 raise RuntimeError("LLM did not return valid JSON")
#         return review

#     def format_review_comment(self, review: Dict[str, Any]) -> str:
#         # Pretty print JSON and a short summary
#         safe = {
#             "code_quality": review.get("code_quality", []),
#             "security_issues": review.get("security_issues", []),
#             "performance_issues": review.get("performance_issues", []),
#             "best_practices": review.get("best_practices", []),
#             "suggested_changes": review.get("suggested_changes", []),
#         }

#         summary_points = []
#         if safe["security_issues"]:
#             summary_points.append(f"Security: {len(safe['security_issues'])} issue(s)")
#         if safe["performance_issues"]:
#             summary_points.append(f"Performance: {len(safe['performance_issues'])} issue(s)")
#         if safe["best_practices"]:
#             summary_points.append(f"Best Practices: {len(safe['best_practices'])} finding(s)")
#         if safe["code_quality"]:
#             summary_points.append(f"Code Quality: {len(safe['code_quality'])} suggestion(s)")
#         if safe["suggested_changes"]:
#             summary_points.append(f"Refactors: {len(safe['suggested_changes'])}")

#         summary_line = " | ".join(summary_points) if summary_points else "No major issues found ✅"

#         return (
#             f"## 🤖 AI Code Review\n"
#             f"**Summary:** {summary_line}\n\n"
#             f"<details>\n<summary>Structured Findings (JSON)</summary>\n\n"
#             f"```json\n{json.dumps(safe, indent=2)}\n```\n"
#             f"</details>\n\n"
#             f"_Model: {self.model}_"
#         )

# backend/review.py

import os
import requests
from typing import Dict, Any
from backend.config import settings

class ReviewEngine:
    def __init__(self):
        # Model & endpoint config
        self.ollama_model = os.getenv("OLLAMA_MODEL", "codellama")
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")

        # Load prompts (optional but nice to guide the model)
        with open(settings.prompts_dir / "review_prompt.txt", "r", encoding="utf-8") as f:
            self.review_template = f.read()

        # Optional: still load refactor prompt, in case you call it later
        refactor_path = settings.prompts_dir / "refactor_prompt.txt"
        self.refactor_template = ""
        if refactor_path.exists():
            with open(refactor_path, "r", encoding="utf-8") as f:
                self.refactor_template = f.read()

    def _chat(self, messages):
        """
        Call Ollama's /api/chat endpoint (non-streaming) and return assistant message text.
        Spec: https://github.com/ollama/ollama/blob/main/docs/api.md#chat
        """
        payload = {
            "model": self.ollama_model,
            "messages": messages,
            "stream": False
        }
        try:
            r = requests.post(self.ollama_url, json=payload, timeout=120)
        except requests.RequestException as e:
            raise RuntimeError(f"Ollama request failed: {e}")

        if r.status_code != 200:
            raise RuntimeError(f"Ollama HTTP {r.status_code}: {r.text}")

        data = r.json()
        # Non-streaming returns a single final message under 'message'
        msg = data.get("message", {})
        content = msg.get("content", "")
        if not content:
            raise RuntimeError("Ollama returned empty content")
        return content

    def review_diff(self, diff_text: str) -> str:
        """
        Returns the *plain chat response* from the Ollama model.
        (No JSON coercion—useful while you iterate or lack quota.)
        """
        system = (
            "You are a senior staff engineer performing rigorous code reviews. "
            "Be concise but thorough. Call out security, performance, readability, and "
            "best-practice issues. Provide concrete, actionable suggestions."
        )
        user = self.review_template.replace("{diff}", diff_text[:200000])  # safety cap
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        return self._chat(messages)

    def format_review_comment(self, chat_text: str) -> str:
        """
        Wrap the chat text for posting as a single PR comment.
        """
        return (
            "## 🤖 AI Code Review (Ollama)\n\n"
            f"{chat_text}\n\n"
            f"_Model: {self.ollama_model}_"
        )