"""Build training examples: (photo, ground-truth JSON) pairs.

Sources
  1. data/ground_truth/*.json + data/pages/*.jpg  (your hand-labelled pages)
  2. --from-db: pages you confirmed in the app (backend/db.sqlite3). Your corrections are
     already baked into those entries, so every page you review makes the next fine-tune better.

Held-out pages (TEST_PAGES) are never used for training, so evaluate.py stays honest.
Light augmentation (tilt, brightness, crop) gives the tiny dataset a few variants per page.
"""
import json
import random
import sqlite3

from PIL import Image, ImageEnhance

from ftcommon import ROOT, answer_json, load_pil, user_message

GT_DIR = ROOT / "data" / "ground_truth"
PAGES_DIR = ROOT / "data" / "pages"
DB_PATH = ROOT / "backend" / "db.sqlite3"
MEDIA_DIR = ROOT / "backend" / "media"
TEST_PAGES = ["page02", "page04", "page06", "page09", "page10"]   # one neat, one messy, one mixed


def augment(img: Image.Image, rng: random.Random) -> Image.Image:
    img = img.rotate(rng.uniform(-3, 3), resample=Image.BICUBIC, expand=True, fillcolor=(255, 255, 255))
    img = ImageEnhance.Brightness(img).enhance(rng.uniform(0.8, 1.2))
    img = ImageEnhance.Contrast(img).enhance(rng.uniform(0.85, 1.15))
    w, h = img.size
    dx, dy = int(w * rng.uniform(0, 0.03)), int(h * rng.uniform(0, 0.03))
    return img.crop((dx, dy, w - dx, h - dy))


def ground_truth_pages(test_pages=TEST_PAGES):
    """Yield (stem, image_path, rows) for labelled pages that are not held out."""
    for f in sorted(GT_DIR.glob("*.json")):
        if f.name.startswith("_") or f.stem in test_pages:
            continue
        img = PAGES_DIR / f"{f.stem}.jpg"
        if img.exists():
            yield f.stem, img, json.loads(f.read_text(encoding="utf-8"))["rows"]


def db_pages():
    """Yield (stem, image_path, rows) for pages confirmed in the app (demo data excluded)."""
    if not DB_PATH.exists():
        return
    con = sqlite3.connect(DB_PATH)
    try:
        pages = con.execute("SELECT id, image FROM api_page WHERE status='confirmed' "
                            "AND model_name NOT LIKE 'demo:%' AND image != ''").fetchall()
        for pid, image in pages:
            path = MEDIA_DIR / image
            entries = con.execute(
                "SELECT e.date_text, c.name, e.item, e.amount, e.type, e.struck_out "
                "FROM api_entry e JOIN api_customer c ON c.id = e.customer_id "
                "WHERE e.page_id = ? ORDER BY e.id", (pid,)).fetchall()
            if path.exists() and entries:
                yield f"db{pid}", path, [
                    {"date": d or None, "name": n, "item": i, "amount": float(a), "type": t,
                     "struck_out": bool(s)} for d, n, i, a, t, s in entries]
    finally:
        con.close()


def build_examples(augment_n: int = 3, from_db: bool = False, test_pages=TEST_PAGES, seed: int = 0):
    """Return a list of chat conversations ready for tinker_cookbook's conversation_to_datum."""
    rng = random.Random(seed)
    sources = list(ground_truth_pages(test_pages)) + (list(db_pages()) if from_db else [])
    examples = []
    for stem, path, rows in sources:
        base = load_pil(path)
        answer = answer_json(rows)
        variants = [base] + [augment(base, rng) for _ in range(augment_n)]
        for img in variants:
            examples.append({"stem": stem, "messages": [
                user_message(img), {"role": "assistant", "content": answer}]})
    return examples


if __name__ == "__main__":
    ex = build_examples()
    print(f"{len(ex)} examples from {len({e['stem'] for e in ex})} pages "
          f"(held out: {', '.join(TEST_PAGES)})")
