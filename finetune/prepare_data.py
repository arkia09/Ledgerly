"""Build the fine-tuning dataset from your labelled pages. Offline: needs no Tinker key.

    python prepare_data.py                      # test pages: page02,page06
    python prepare_data.py --test page01,page04 --variants 24

Pages in --test are NEVER used for training, so the comparison is on photos the model has not seen.
Each training page becomes `variants` augmented photos (variant 0 is the untouched original).
Output: data/finetune/train/*.jpg, train.jsonl and split.json.
"""
import argparse
import json
import shutil
import zlib

import common as c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", default="page02,page06", help="comma-separated page stems held out for testing")
    ap.add_argument("--variants", type=int, default=16, help="augmented copies per training page")
    args = ap.parse_args()

    available = c.ground_truth_pages()
    test = [s for s in args.test.split(",") if s]
    unknown = [s for s in test if s not in available]
    if unknown:
        raise SystemExit(f"--test names with no ground truth: {unknown}. Available: {available}")
    train = [s for s in available if s not in test]
    if not train:
        raise SystemExit("No pages left for training.")

    train_dir = c.WORK / "train"
    shutil.rmtree(train_dir, ignore_errors=True)
    train_dir.mkdir(parents=True)

    lines = []
    for stem in train:
        img_path = c.find_image(stem)
        if img_path is None:
            print(f"skip {stem}: no photo in data/pages"); continue
        gt = json.loads((c.GROUND_TRUTH / f"{stem}.json").read_text(encoding="utf-8"))
        target = c.target_json(gt["rows"])
        base = c.load_image(img_path)
        for v in range(args.variants):
            img = base if v == 0 else c.augment(base, seed=zlib.crc32(f"{stem}:{v}".encode()))
            out = train_dir / f"{stem}_v{v:02d}.jpg"
            img.save(out, "JPEG", quality=92)
            lines.append({"image": out.name, "page": stem, "target": target})

    (c.WORK / "train.jsonl").write_text("\n".join(json.dumps(l, ensure_ascii=False) for l in lines), encoding="utf-8")
    (c.WORK / "split.json").write_text(json.dumps({"train": train, "test": test}, indent=2), encoding="utf-8")
    print(f"train pages: {train}\ntest pages:  {test}\nexamples written: {len(lines)} -> {c.WORK}")
    if len(train) < 10:
        print("\nNote: only %d labelled training pages. Label more (see README) for a trustworthy result." % len(train))


if __name__ == "__main__":
    main()
