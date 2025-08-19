import os
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]
PROMPTS_DIR = BASE_DIR / "prompts"

@dataclass
class Settings:
    github_webhook_secret: str = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    github_token: str = os.getenv("GITHUB_TOKEN", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    openai_base: str = os.getenv("OPENAI_BASE", "https://api.openai.com/v1")
    prompts_dir: Path = PROMPTS_DIR

settings = Settings()
