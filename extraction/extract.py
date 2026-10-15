"""Extract ledger rows from one page photo using a local Gemma model via Ollama.

Usage:
    python extract.py ../data/pages/page01.jpg
    KHATA_MODEL=gemma4:e2b python extract.py ../data/pages/page01.jpg
"""
import json
import os
import sys
import time
from pathlib import Path

import ollama

from preprocess import load_image_bytes
from schema import Page

HERE = Path(__file__).parent
PROMPT_PATH = HERE / "prompt.txt"

MODEL = os.environ.get("KHATA_MODEL", "gemma4:e4b")
NUM_CTX = int(os.environ.get("KHATA_NUM_CTX", "8192"))
MAX_SIDE = int(os.environ.get("KHATA_MAX_SIDE", "1280"))
MAX_TOKENS = int(os.environ.get("KHATA_MAX_TOKENS", "4096"))


class ExtractionError(Exception):
    def __init__(self, message: str, raw: str = ""):
        super().__init__(message)
        self.raw = raw


def build_prompt(extra_rules: list[str] | None = None) -> str:
    """Read prompt.txt fresh each call so you can edit it between runs.
    extra_rules is where Step 2's 'mistakes to avoid' corrections go."""
    text = PROMPT_PATH.read_text(encoding="utf-8")
    if extra_rules:
        text += "\n\nMistakes to avoid (from earlier corrections):\n"
        text += "\n".join(f"- {r}" for r in extra_rules)
    return text


def extract(image_path: str, model: str = MODEL,
            extra_rules: list[str] | None = None) -> tuple[Page, float]:
    """Returns (Page, seconds taken by the model call)."""
    kwargs = dict(
        model=model,
        messages=[{
            "role": "user",
            "content": build_prompt(extra_rules),
            "images": [load_image_bytes(image_path, MAX_SIDE)],
        }],
        format=Page.model_json_schema(),  # constrains output to valid JSON
        options={"temperature": 0, "num_ctx": NUM_CTX, "num_predict": MAX_TOKENS},
    )
    start = time.perf_counter()
    try:
        resp = ollama.chat(think=False, **kwargs)  # skip reasoning tokens: faster on CPU
    except TypeError:
        resp = ollama.chat(**kwargs)               # older client without `think`
    seconds = time.perf_counter() - start

    raw = resp["message"]["content"]
    try:
        return Page.model_validate_json(raw), seconds
    except Exception as e:
        raise ExtractionError(f"Model output did not match schema: {e}", raw)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python extract.py <image>")
    try:
        page, secs = extract(sys.argv[1])
    except ExtractionError as e:
        print("FAILED:", e, file=sys.stderr)
        print("--- raw model output ---\n" + e.raw, file=sys.stderr)
        sys.exit(1)
    print(json.dumps(page.model_dump(), indent=2, ensure_ascii=False))
    print(f"\n[{MODEL}] {len(page.rows)} rows in {secs:.1f}s", file=sys.stderr)
