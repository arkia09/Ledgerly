"""Shared pieces for the Tinker fine-tuning pipeline.

Training and inference MUST build the prompt and preprocess the image the same way, so both
go through the helpers here.

Needs:  pip install tinker tinker-cookbook   and   TINKER_API_KEY in the environment.
NOTE: this folder is called `ft`, not `tinker`, so it cannot shadow the SDK package.
"""
import io
import json
import os
import re
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
EXTRACTION = HERE.parent
ROOT = EXTRACTION.parent
# extraction/*.py uses flat imports ("from schema import Page"); put it first on sys.path
# (PyPI has an unrelated package called "schema").
if str(EXTRACTION) not in sys.path:
    sys.path.insert(0, str(EXTRACTION))

from preprocess import load_image_bytes  # noqa: E402
from schema import Page  # noqa: E402

BASE_MODEL = os.environ.get("TINKER_BASE_MODEL", "Qwen/Qwen3.6-35B-A3B")
MAX_SIDE = int(os.environ.get("TINKER_MAX_SIDE", "1024"))   # fewer image tokens = cheaper
MODEL_FILE = HERE / "last_model.json"                        # written by train.py


def build_prompt(extra_rules=None) -> str:
    text = (EXTRACTION / "prompt.txt").read_text(encoding="utf-8")
    if extra_rules:
        text += "\n\nMistakes to avoid (from earlier corrections):\n"
        text += "\n".join(f"- {r}" for r in extra_rules)
    return text


def load_pil(path) -> Image.Image:
    """Same preprocessing the Ollama path uses (EXIF rotate, shrink, autocontrast)."""
    return Image.open(io.BytesIO(load_image_bytes(str(path), MAX_SIDE))).convert("RGB")


def user_message(image: Image.Image, extra_rules=None) -> dict:
    return {"role": "user", "content": [
        {"type": "image", "image": image},
        {"type": "text", "text": build_prompt(extra_rules)}]}


def answer_json(rows: list[dict]) -> str:
    """Ground-truth/corrected rows -> the exact JSON string the model should produce."""
    out = []
    for r in rows:
        raw = " ".join(str(x) for x in (r.get("date"), r.get("name"), r.get("item"),
                                        _num(r.get("amount"))) if x not in (None, ""))
        out.append({"raw_text": raw, "date": r.get("date"), "name": r.get("name"),
                    "item": r.get("item"), "amount": r.get("amount"), "type": r["type"],
                    "struck_out": bool(r.get("struck_out")), "confidence": 1.0})
    return Page(rows=out, page_total=None).model_dump_json()


def _num(v):
    return int(v) if isinstance(v, float) and v.is_integer() else v


def parse_page(text: str) -> Page:
    """Model text -> Page. Tolerates ```json fences and chatter around the JSON."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in model output")
    return Page.model_validate(json.loads(text[start:end + 1]))


def load_model_info() -> dict:
    if not MODEL_FILE.exists():
        raise FileNotFoundError(f"{MODEL_FILE.name} not found: run `python ft/train.py` first.")
    return json.loads(MODEL_FILE.read_text(encoding="utf-8"))
