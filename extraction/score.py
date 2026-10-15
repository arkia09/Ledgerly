"""Score a batch run against your hand-written ground truth.

Usage:
    python score.py --run gemma4_e4b
Ground truth files live in data/ground_truth/<image-stem>.json (see _template.json).
"""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from rapidfuzz import fuzz

ROOT = Path(__file__).resolve().parent.parent
GT_DIR = ROOT / "data" / "ground_truth"
OUT_DIR = ROOT / "data" / "outputs"
GATE = 0.70  # name AND amount both right, on neat pages


def norm_text(s):
    return re.sub(r"\s+", " ", (s or "").strip().casefold())


def norm_date(s):
    if not s:
        return ""
    parts = [p.lstrip("0") for p in re.split(r"[\s\-./]+", s.strip().casefold()) if p]
    return "/".join(parts)


def same_amount(a, b):
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) < 0.01


def pair_score(gt, pr):
    name = fuzz.ratio(norm_text(gt.get("name")), norm_text(pr.get("name"))) / 100
    amt = 0.4 if same_amount(gt.get("amount"), pr.get("amount")) else 0.0
    return 0.6 * name + amt


def match_rows(gt_rows, pr_rows):
    """Greedy best-first matching. Returns {gt_index: pred_index}."""
    pairs = sorted(
        ((pair_score(g, p), gi, pi)
         for gi, g in enumerate(gt_rows) for pi, p in enumerate(pr_rows)),
        reverse=True)
    used_g, used_p, result = set(), set(), {}
    for score, gi, pi in pairs:
        if score < 0.35:
            break
        if gi in used_g or pi in used_p:
            continue
        used_g.add(gi); used_p.add(pi); result[gi] = pi
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--details", action="store_true",
                    help="print every wrong field: what you wrote vs what the model said")
    args = ap.parse_args()

    stats = defaultdict(lambda: defaultdict(int))
    times = []
    for gt_file in sorted(GT_DIR.glob("*.json")):
        if gt_file.name.startswith("_"):
            continue
        out_file = OUT_DIR / args.run / gt_file.name
        if not out_file.exists():
            print(f"(no output yet for {gt_file.stem}, skipping)")
            continue
        gt = json.loads(gt_file.read_text(encoding="utf-8"))
        rec = json.loads(out_file.read_text(encoding="utf-8"))
        ptype = gt.get("page_type", "unspecified")
        gt_rows = gt["rows"]
        pr_rows = rec.get("page", {}).get("rows", []) if "error" not in rec else []
        if "seconds" in rec:
            times.append(rec["seconds"])

        m = match_rows(gt_rows, pr_rows)
        if args.details:
            print(f"\n== {gt_file.stem} ({ptype}) ==")
            for pi, p in enumerate(pr_rows):
                if pi not in m.values():
                    print(f"  EXTRA model row not in your key: {p.get('raw_text')!r}")
        for key in (ptype, "ALL"):
            s = stats[key]
            s["pages"] += 1
            s["gt_rows"] += len(gt_rows)
            s["matched"] += len(m)
            s["extra"] += len(pr_rows) - len(m)
            for gi, g in enumerate(gt_rows):
                p = pr_rows[m[gi]] if gi in m else None
                ok = {
                    "name": bool(p) and norm_text(g.get("name")) == norm_text(p.get("name")),
                    "amount": bool(p) and same_amount(g.get("amount"), p.get("amount")),
                    "date": bool(p) and norm_date(g.get("date")) == norm_date(p.get("date")),
                    "type": bool(p) and g.get("type") == p.get("type"),
                    "struck": bool(p) and bool(g.get("struck_out")) == bool(p.get("struck_out")),
                }
                for f, v in ok.items():
                    s[f] += v
                s["name_and_amount"] += ok["name"] and ok["amount"]
                s["fully_correct"] += all(ok.values())
                if args.details and key == "ALL":
                    if p is None:
                        print(f"  row {gi+1}: MISSED  (you wrote {g.get('name')!r}, {g.get('amount')})")
                    elif not all(ok.values()):
                        keys = {"name": "name", "amount": "amount", "date": "date",
                                "type": "type", "struck": "struck_out"}
                        diffs = [f"{f}: wrote {g.get(k)!r} -> model {p.get(k)!r}"
                                 for f, k in keys.items() if not ok[f]]
                        print(f"  row {gi+1}: " + " | ".join(diffs))

    if not stats:
        raise SystemExit("Nothing to score. Add ground truth files and run batch.py first.")

    def pct(n, d):
        return f"{100 * n / d:5.1f}%" if d else "   n/a"

    print(f"\nRun: {args.run}")
    header = f"{'page type':<12}{'pages':>6}{'rows':>6}{'found':>7}{'extra':>7}" \
             f"{'name':>8}{'amount':>8}{'date':>8}{'type':>8}{'struck':>8}{'full row':>10}"
    print(header); print("-" * len(header))
    for key in [k for k in stats if k != "ALL"] + ["ALL"]:
        s = stats[key]; d = s["gt_rows"]
        print(f"{key:<12}{s['pages']:>6}{d:>6}{s['matched']:>7}{s['extra']:>7}"
              f"{pct(s['name'], d):>8}{pct(s['amount'], d):>8}{pct(s['date'], d):>8}"
              f"{pct(s['type'], d):>8}{pct(s['struck'], d):>8}{pct(s['fully_correct'], d):>10}")
    if times:
        print(f"\nAvg time per page: {sum(times)/len(times):.1f}s  (n={len(times)})")

    neat = stats.get("neat")
    if neat and neat["gt_rows"]:
        r = neat["name_and_amount"] / neat["gt_rows"]
        verdict = "PASS" if r >= GATE else "FAIL"
        print(f"\nGATE (neat pages, name AND amount right): {r*100:.1f}% "
              f"vs {GATE*100:.0f}% -> {verdict}")
    else:
        print('\nGATE: no pages with "page_type": "neat" yet.')


if __name__ == "__main__":
    main()