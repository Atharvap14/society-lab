from dataclasses import dataclass
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]

@dataclass
class Settings:
    root: Path = ROOT
    model: str = "gpt-5.4-mini"
    max_calls: int = 400
    max_output_tokens: int = 2000
    max_tool_rounds: int = 5
    max_workers: int = 3

    @property
    def runtime(self):
        p = self.root / ".runtime"
        p.mkdir(exist_ok=True, parents=True)
        return p

    def api_key(self):
        key = os.environ.get("OPENAI_API_KEY", "").strip()
        p = self.root / ".secrets/openai-api-key.txt"
        if not key and p.is_file():
            key = p.read_text().strip()
        if not key:
            raise RuntimeError("Set OPENAI_API_KEY or create .secrets/openai-api-key.txt")
        return key
