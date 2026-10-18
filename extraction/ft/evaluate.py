"""Compare the untouched base model with your fine-tuned one on the held-out pages.

    python ft/evaluate.py                 # runs both, saves outputs, prints both score tables
Outputs go to data/outputs/tinker_base/ and data/outputs/tinker_ft/ in the same format as
batch.py, so extraction/score.py reads them. Add your Ollama Gemma run for a 3-way comparison:
    python score.py --run gemma4_e4b --pages page02,page04,page06
"""
import json
import subprocess
import sys

from ftcommon import EXTRACTION, ROOT
from dataset import TEST_PAGES
import sampler


def run(name: str, finetuned: bool):
    out = ROOT / "data" / "outputs" / name
    out.mkdir(parents=True, exist_ok=True)
    for stem in TEST_PAGES:
        img = ROOT / "data" / "pages" / f"{stem}.jpg"
        try:
            page, secs = sampler.extract(str(img), finetuned=finetuned)
            rec = {"model": name, "seconds": secs, "page": page.model_dump()}
        except Exception as e:
            rec = {"model": name, "error": str(e), "raw": getattr(e, "raw", "")}
        (out / f"{stem}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"{name}: {stem} {'ERROR ' + rec['error'][:60] if 'error' in rec else f'{secs:.1f}s'}")


def main():
    for name, ft in (("tinker_base", False), ("tinker_ft", True)):
        run(name, ft)
    for name in ("tinker_base", "tinker_ft"):
        subprocess.run([sys.executable, str(EXTRACTION / "score.py"), "--run", name,
                        "--pages", ",".join(TEST_PAGES)], check=False)


if __name__ == "__main__":
    main()
