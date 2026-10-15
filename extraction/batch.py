"""Run extraction over every image in data/pages and save results + timings.

Usage:
    python batch.py                    # run name = model tag
    python batch.py --run e4b_v2       # name this run (so you can compare prompts)
    python batch.py --limit 3          # just the first 3 pages
    python batch.py --force            # redo pages that already have output
Safe to stop and restart: finished pages are skipped.
"""
import argparse
import json
import re
from pathlib import Path

import extract as ex

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "data" / "pages"
OUT = ROOT / "data" / "outputs"
EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=None)
    ap.add_argument("--model", default=ex.MODEL)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    run = args.run or re.sub(r"[^\w.-]+", "_", args.model)
    out_dir = OUT / run
    out_dir.mkdir(parents=True, exist_ok=True)

    images = sorted(p for p in PAGES.iterdir() if p.suffix.lower() in EXTS)
    if args.limit:
        images = images[: args.limit]
    if not images:
        raise SystemExit(f"No images found in {PAGES}")

    times = []
    for i, img in enumerate(images, 1):
        target = out_dir / f"{img.stem}.json"
        if target.exists() and not args.force:
            try:
                already_ok = "error" not in json.loads(target.read_text(encoding="utf-8"))
            except Exception:
                already_ok = False
            if already_ok:
                print(f"[{i}/{len(images)}] {img.name}: skipped (already done)")
                continue
        print(f"[{i}/{len(images)}] {img.name} ...", flush=True)
        try:
            page, secs = ex.extract(str(img), model=args.model)
            record = {"model": args.model, "seconds": round(secs, 1),
                      "page": page.model_dump()}
            times.append(secs)
            print(f"    {len(page.rows)} rows, {secs:.1f}s")
        except Exception as e:
            record = {"model": args.model, "error": str(e),
                      "raw": getattr(e, "raw", "")}
            print(f"    FAILED: {e}")
        target.write_text(json.dumps(record, indent=2, ensure_ascii=False),
                          encoding="utf-8")

    if times:
        print(f"\nDone. avg {sum(times)/len(times):.1f}s/page over {len(times)} pages "
              f"-> {out_dir}")


if __name__ == "__main__":
    main()
    