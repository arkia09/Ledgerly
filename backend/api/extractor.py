"""Bridge to the frozen Step 1 extraction code.

extraction/*.py uses flat imports ("from schema import Page"), so that folder has to be on
sys.path. It goes at the FRONT: PyPI has an unrelated package called "schema" that would
otherwise win the import.
"""
import json
import os
import sys
from pathlib import Path

from django.conf import settings

FAKE_FALLBACK_STEM = "page01"


def fake_mode() -> bool:
    """Read at call time so the env var can be changed without touching code."""
    return os.environ.get("LEDGERLY_FAKE_EXTRACT", "").strip().lower() in {"1", "true", "yes", "on"}


def load():
    """Import and return the extraction.extract module (imports ollama, so keep it lazy)."""
    d = str(settings.LEDGERLY_EXTRACTION_DIR)
    if d not in sys.path:
        sys.path.insert(0, d)
    import extract
    return extract


def _fake_extract(original_name: str):
    out_dir = Path(settings.LEDGERLY_FAKE_OUTPUT_DIR)
    # Look the file up in the directory listing rather than building a path from user input.
    files = {p.stem.lower(): p for p in out_dir.glob("*.json")} if out_dir.is_dir() else {}
    stem = Path(original_name or "").stem.lower()
    chosen = files.get(stem) or files.get(FAKE_FALLBACK_STEM)
    if chosen is None:
        raise FileNotFoundError(
            f"LEDGERLY_FAKE_EXTRACT is on but no saved output was found in {out_dir} "
            f"(looked for '{stem}.json' and '{FAKE_FALLBACK_STEM}.json').")
    record = json.loads(chosen.read_text(encoding="utf-8"))
    if "page" not in record:
        raise ValueError(f"{chosen.name} is a failed run, not a saved extraction.")
    return record["page"], float(record.get("seconds") or 0.0), f"fake:{chosen.stem}"


def backend_name() -> str:
    """'ollama' (default, photos stay on this computer) or 'tinker' (opt-in, photos are sent to
    Tinker's cloud to be read by your fine-tuned model)."""
    return os.environ.get("LEDGERLY_EXTRACTOR", "ollama").strip().lower()


def _tinker_extract(image_path: str, rules: list[str]):
    ft = str(settings.LEDGERLY_EXTRACTION_DIR / "ft")
    if ft not in sys.path:
        sys.path.insert(0, ft)
    import sampler
    from ftcommon import load_model_info
    page, seconds = sampler.extract(image_path, finetuned=True, extra_rules=rules or None)
    return page.model_dump(), seconds, f"tinker:{load_model_info()['base_model']}"


def run_extraction(image_path: str, original_name: str, rules: list[str]):
    """Returns (page_dict, seconds, model_name). Raises on any failure; callers must not hide it."""
    if fake_mode():
        return _fake_extract(original_name)
    if backend_name() == "tinker":
        return _tinker_extract(image_path, rules)
    mod = load()
    page, seconds = mod.extract(image_path, extra_rules=rules or None)
    return page.model_dump(), seconds, mod.MODEL
