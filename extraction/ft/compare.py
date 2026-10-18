"""Build one self-contained HTML page that compares model runs against your ground truth.

    python ft/compare.py                      # gemma4_e4b vs tinker_base vs tinker_ft on the held-out pages
    python ft/compare.py --pages page04       # just one page
    python ft/compare.py --runs gemma4_e4b,tinker_ft --out data/my_compare.html

It reads data/outputs/<run>/<page>.json
and data/ground_truth/<page>.json, then writes data/compare.html and opens it.

It uses the matching and field checks from score.py, so every number here agrees with
`python score.py --run <name> --pages ...`. The "item" field is shown but not judged,
because score.py does not judge it either.
"""
import argparse
import base64
import html
import io
import json
import sys
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXTRACTION = HERE.parent
ROOT = EXTRACTION.parent
if str(EXTRACTION) not in sys.path:
    sys.path.insert(0, str(EXTRACTION))

from score import match_rows, norm_date, norm_text, same_amount  # noqa: E402

GT_DIR = ROOT / "data" / "ground_truth"
OUT_DIR = ROOT / "data" / "outputs"
PAGES_DIR = ROOT / "data" / "pages"

DEFAULT_RUNS = ["gemma4_e4b", "tinker_base", "tinker_ft"]
FALLBACK_PAGES = ["page02", "page04", "page06"]
LABELS = {
    "gemma4_e4b": "Gemma 4 (local, Ollama)",
    "tinker_base": "Qwen3.6 base (Tinker)",
    "tinker_ft": "Qwen3.6 fine-tuned (Tinker)",
}
FIELDS = ("name", "amount", "date", "type", "struck")


def default_pages() -> list[str]:
    try:  # keep in sync with the training script when the SDK is installed
        from dataset import TEST_PAGES  # type: ignore
        return list(TEST_PAGES)
    except Exception:
        return FALLBACK_PAGES


def esc(x) -> str:
    return html.escape("" if x is None else str(x))


def num(x) -> str:
    if x is None:
        return "blank"
    f = float(x)
    return f"{f:g}"


def check_row(g: dict, p: dict) -> dict:
    return {
        "name": norm_text(g.get("name")) == norm_text(p.get("name")),
        "amount": same_amount(g.get("amount"), p.get("amount")),
        "date": norm_date(g.get("date")) == norm_date(p.get("date")),
        "type": g.get("type") == p.get("type"),
        "struck": bool(g.get("struck_out")) == bool(p.get("struck_out")),
    }


def load_run(run: str, stem: str):
    f = OUT_DIR / run / f"{stem}.json"
    if not f.exists():
        return None
    return json.loads(f.read_text(encoding="utf-8"))


def evaluate(gt_rows: list[dict], rec: dict | None) -> dict:
    """Score one run on one page. Returns everything the HTML needs."""
    if rec is None:
        return {"state": "missing", "rows": {}, "extras": [], "full": 0, "seconds": None}
    if "error" in rec:
        return {"state": "error", "error": rec["error"], "rows": {}, "extras": [], "full": 0,
                "seconds": None}
    pr_rows = rec.get("page", {}).get("rows", [])
    m = match_rows(gt_rows, pr_rows)
    rows = {gi: (pr_rows[pi], check_row(gt_rows[gi], pr_rows[pi])) for gi, pi in m.items()}
    extras = [p for pi, p in enumerate(pr_rows) if pi not in m.values()]
    full = sum(all(c.values()) for _, c in rows.values())
    return {"state": "ok", "rows": rows, "extras": extras, "full": full,
            "seconds": rec.get("seconds")}


# ---------- HTML pieces ----------

def gt_cell(g: dict, i: int) -> str:
    struck = ' <span class="tag">crossed out</span>' if g.get("struck_out") else ""
    return (f'<td class="gt"><div class="l1"><b>{esc(g.get("name"))}</b>'
            f'<span class="amt">{num(g.get("amount"))}</span></div>'
            f'<div class="l2"><span>{esc(g.get("date") or "no date")}</span>'
            f'<span>{esc(g.get("type"))}</span><span class="item">{esc(g.get("item") or "")}</span>'
            f'{struck}</div></td>')


def field(cls: str, ok: bool, shown: str) -> str:
    return f'<span class="f {cls} {"ok" if ok else "bad"}">{esc(shown)}</span>'


def run_cell(g: dict, ev: dict, gi: int) -> str:
    if ev["state"] != "ok":
        return '<td class="run miss">no result</td>'
    if gi not in ev["rows"]:
        return '<td class="run miss">Missed this row</td>'
    p, ok = ev["rows"][gi]
    shown_name = p.get("name") or "(blank)"
    l1 = field("name", ok["name"], shown_name) + field("amount", ok["amount"], num(p.get("amount")))
    l2 = field("date", ok["date"], p.get("date") or "(none)") + field("type", ok["type"], p.get("type"))
    if p.get("item"):
        l2 += f'<span class="item">{esc(p.get("item"))}</span>'
    if p.get("struck_out") or not ok["struck"]:
        l2 += field("struck", ok["struck"], "crossed out" if p.get("struck_out") else "not crossed out")
    notes = []
    if not ok["name"]:
        notes.append(f'name should be {esc(g.get("name"))}')
    if not ok["amount"]:
        notes.append(f'amount should be {num(g.get("amount"))}')
    if not ok["date"]:
        notes.append(f'date should be {esc(g.get("date") or "none")}')
    if not ok["type"]:
        notes.append(f'type should be {esc(g.get("type"))}')
    if not ok["struck"]:
        notes.append("should be crossed out" if g.get("struck_out") else "should not be crossed out")
    note_html = f'<div class="exp">{"; ".join(notes)}</div>' if notes else ""
    return f'<td class="run"><div class="l1">{l1}</div><div class="l2">{l2}</div>{note_html}</td>'


def run_head(run: str, ev: dict, n_rows: int) -> str:
    label = esc(LABELS.get(run, run))
    if ev["state"] == "missing":
        return f'<th class="runhead"><div class="rname">{label}</div><div class="sub">no output for this page</div></th>'
    if ev["state"] == "error":
        return (f'<th class="runhead"><div class="rname">{label}</div>'
                f'<div class="sub bad-t">error: {esc(ev["error"][:80])}</div></th>')
    secs = f' · {ev["seconds"]:.1f}s' if ev["seconds"] is not None else ""
    return (f'<th class="runhead"><div class="rname">{label}</div>'
            f'<div class="score">{ev["full"]}/{n_rows} rows fully correct</div>'
            f'<div class="sub">{len(ev["rows"])} found, {len(ev["extras"])} extra{secs}</div></th>')


def photo_data_uri(stem: str) -> str | None:
    f = PAGES_DIR / f"{stem}.jpg"
    if not f.exists():
        return None
    from PIL import Image, ImageOps
    img = ImageOps.exif_transpose(Image.open(f)).convert("RGB")
    img.thumbnail((1500, 1500))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=78)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def page_section(stem: str, gt: dict, runs: list[str], evs: dict) -> str:
    rows = gt["rows"]
    head = "".join(run_head(r, evs[r], len(rows)) for r in runs)
    body = []
    for gi, g in enumerate(rows):
        all_good = all(evs[r]["state"] == "ok" and gi in evs[r]["rows"]
                       and all(evs[r]["rows"][gi][1].values()) for r in runs)
        cells = "".join(run_cell(g, evs[r], gi) for r in runs)
        body.append(f'<tr class="{"allgood" if all_good else ""}"><td class="n">{gi + 1}</td>'
                    f'{gt_cell(g, gi)}{cells}</tr>')
    extra_cells = []
    for r in runs:
        ex = evs[r]["extras"]
        if ex:
            items = "".join(f'<div>{esc(p.get("raw_text") or p.get("name"))}</div>' for p in ex)
            extra_cells.append(f'<td class="run extra"><b>Extra rows not in your book</b>{items}</td>')
        else:
            extra_cells.append('<td class="run"></td>')
    if any(evs[r]["extras"] for r in runs):
        body.append(f'<tr><td class="n"></td><td class="gt"></td>{"".join(extra_cells)}</tr>')
    img = photo_data_uri(stem)
    photo = (f'<aside class="photo"><img src="{img}" alt="{esc(stem)} photo" title="Click to zoom"></aside>'
             if img else "")
    ptype = esc(gt.get("page_type", ""))
    return (f'<section class="pane" id="pane-{esc(stem)}"><h2>{esc(stem)} <small>{ptype}, '
            f'{len(rows)} rows</small></h2><div class="split">{photo}'
            f'<div class="tablewrap"><table><thead><tr><th class="n">#</th>'
            f'<th class="gthead">Your book (truth)</th>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div></div></section>')


def overview_section(runs: list[str], pages: list[str], gts: dict, all_evs: dict) -> str:
    total_rows = sum(len(gts[s]["rows"]) for s in pages)
    stats = {}
    for r in runs:
        s = dict.fromkeys(FIELDS, 0)
        s.update(full=0, extra=0, found=0, secs=[], pages_ok=0)
        for stem in pages:
            ev = all_evs[stem][r]
            if ev["state"] != "ok":
                continue
            s["pages_ok"] += 1
            s["extra"] += len(ev["extras"])
            s["found"] += len(ev["rows"])
            s["full"] += ev["full"]
            if ev["seconds"] is not None:
                s["secs"].append(ev["seconds"])
            for _, ck in ev["rows"].values():
                for f in FIELDS:
                    s[f] += ck[f]
        stats[r] = s

    def best(key, lower=False):
        vals = {r: (sum(stats[r]["secs"]) / len(stats[r]["secs"]) if key == "secs" and stats[r]["secs"]
                    else stats[r].get(key)) for r in runs if stats[r]["pages_ok"]}
        vals = {r: v for r, v in vals.items() if isinstance(v, (int, float))}
        if not vals:
            return None
        return (min if lower else max)(vals.values())

    cols = [("full", "Full row"), ("name", "Name"), ("amount", "Amount"), ("date", "Date"),
            ("type", "Type"), ("struck", "Crossed out")]
    bests = {k: best(k) for k, _ in cols}
    best_extra, best_secs = best("extra", True), best("secs", True)
    head = "".join(f"<th>{lbl}</th>" for _, lbl in cols) + "<th>Extra rows</th><th>Avg seconds / page</th>"
    lines = []
    for r in runs:
        s = stats[r]
        if not s["pages_ok"]:
            lines.append(f'<tr><th class="rowhead">{esc(LABELS.get(r, r))}</th>'
                         f'<td colspan="{len(cols) + 2}" class="muted">no outputs found</td></tr>')
            continue
        tds = ""
        for k, _ in cols:
            v = s[k]
            win = " win" if v == bests[k] and len(runs) > 1 else ""
            tds += f'<td class="{win.strip()}">{v}/{total_rows}<small>{100 * v / total_rows:.0f}%</small></td>'
        win_e = "win" if s["extra"] == best_extra and len(runs) > 1 else ""
        avg = sum(s["secs"]) / len(s["secs"]) if s["secs"] else None
        win_s = "win" if avg is not None and avg == best_secs and len(runs) > 1 else ""
        tds += f'<td class="{win_e}">{s["extra"]}</td>'
        tds += f'<td class="{win_s}">{f"{avg:.1f}s" if avg is not None else "n/a"}</td>'
        lines.append(f'<tr><th class="rowhead">{esc(LABELS.get(r, r))}</th>{tds}</tr>')
    return (f'<section class="pane" id="pane-overview"><h2>Scoreboard <small>{len(pages)} held-out pages, '
            f'{total_rows} rows, never used for training</small></h2>'
            f'<div class="tablewrap"><table class="score"><thead><tr><th></th>{head}</tr></thead>'
            f'<tbody>{"".join(lines)}</tbody></table></div>'
            f'<p class="fine">Green = best in that column. "Full row" needs name, amount, date, type and '
            f'crossed-out flag all right. Same checks as score.py. Small test set, so read differences of one '
            f'or two rows as noise.</p></section>')


CSS = """
:root{color-scheme:light;--ink:#3a2a1f;--muted:#7a6753;--page:#f6ecd8;--slip:#fbf5e8;--rule:#d9c5a6;
--rule2:#b79a76;--leather:#7b5640;--red:#b0463b;--redbg:#f4d9d2;--green:#46703d;--greenbg:#dcebd3;--hand:'Kalam','Segoe Print','Bradley Hand',cursive;
--serif:'Source Serif 4',Georgia,'Noto Serif',serif}
*{box-sizing:border-box}
body{margin:0;background:#c9ae8c;font:17px/1.45 var(--serif);color:var(--ink);padding:1.2rem}
.book{max-width:1500px;margin:0 auto;background:var(--page);border-radius:6px;box-shadow:0 10px 40px #0004;
padding:1.4rem 1.8rem 2rem 2.6rem;position:relative;
background-image:repeating-linear-gradient(to bottom,transparent 0 31px,#7a563c1a 31px 32px)}
.book::before{content:"";position:absolute;left:1.5rem;top:0;bottom:0;width:5px;border-left:1.5px solid #b0463b99;border-right:1.5px solid #b0463b99}
h1{font:700 2rem var(--hand);margin:0}
h2{font:700 1.45rem var(--hand);margin:.2rem 0 .8rem}
h2 small{font:400 .95rem var(--serif);color:var(--muted);margin-left:.5rem}
.top{display:flex;justify-content:space-between;align-items:flex-end;gap:1rem;flex-wrap:wrap;margin-bottom:.8rem}
.top p{margin:.1rem 0;color:var(--muted)}
.tabs{display:flex;gap:.4rem;flex-wrap:wrap;margin:.4rem 0 1rem}
.tabs button{font:600 1rem var(--hand);border:1.5px solid var(--rule2);background:var(--slip);color:var(--ink);
padding:.45rem 1.1rem;border-radius:8px 8px 0 0;cursor:pointer}
.tabs button.on{background:var(--leather);border-color:var(--leather);color:#fbf1de}
.opts{margin-left:auto;display:flex;align-items:center;gap:.5rem;font-size:.95rem}
.pane{display:none}.pane.on{display:block}
.split{display:grid;grid-template-columns:minmax(220px,300px) 1fr;gap:1.2rem;align-items:start}
.photo{position:sticky;top:1rem;background:#fffdf7;padding:.6rem;border:1px solid var(--rule);box-shadow:0 3px 10px #0002}
.photo img{width:100%;display:block;cursor:zoom-in}
.photo img.zoom{position:fixed;inset:1rem;width:auto;max-width:calc(100vw - 2rem);max-height:calc(100vh - 2rem);margin:auto;
object-fit:contain;background:#fffdf7;z-index:50;box-shadow:0 0 0 100vmax #000a;cursor:zoom-out}
.tablewrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;min-width:760px}
thead th{font:700 1rem var(--hand);text-align:left;vertical-align:bottom;padding:.5rem .7rem;border-bottom:3px double var(--rule2)}
.runhead .rname{font-size:1.05rem}.runhead .score{font:600 .95rem var(--serif);color:var(--ink)}
.sub{font:400 .85rem var(--serif);color:var(--muted)}.bad-t{color:var(--red)}
td{padding:.55rem .7rem;border-bottom:1px solid var(--rule);vertical-align:top}
td.n,th.n{width:2.2rem;color:var(--muted);text-align:right;border-right:3px double var(--rule2)}
td.gt{background:#efe0c288;border-right:3px double var(--rule2);min-width:180px}
td.run{min-width:200px;border-right:1px solid var(--rule)}
.l1{display:flex;gap:.4rem;flex-wrap:wrap;align-items:baseline}.l2{display:flex;gap:.35rem;flex-wrap:wrap;margin-top:.25rem;font-size:.9rem;color:var(--muted)}
.amt{font-weight:700;margin-left:auto;font-variant-numeric:tabular-nums}
.f{padding:.05rem .45rem;border-radius:4px}
.f.ok{background:var(--greenbg);color:var(--green)}.f.bad{background:var(--redbg);color:var(--red);font-weight:600}
.f.name,.f.amount{font-size:1rem;font-weight:600}
.item{color:var(--ink);font-style:italic}
.tag{background:#e6d2b0;border-radius:4px;padding:0 .4rem;font-size:.8rem}
.exp{margin-top:.3rem;font-size:.85rem;color:var(--red)}
.miss{color:var(--red);font-style:italic;background:var(--redbg)}
.extra{color:var(--red);font-size:.9rem}.extra b{display:block;margin-bottom:.2rem}
body.only-bad tr.allgood{display:none}
table.score td,table.score th{text-align:center;font-variant-numeric:tabular-nums;font-size:1.05rem}
table.score th.rowhead{text-align:left;font:700 1.05rem var(--hand)}
table.score td small{display:block;color:var(--muted);font-size:.8rem}
table.score td.win{background:var(--greenbg);color:var(--green);font-weight:700}
.muted{color:var(--muted)}.fine{color:var(--muted);font-size:.9rem;max-width:70ch}
@media (max-width:900px){.split{grid-template-columns:1fr}.photo{position:static;max-width:320px}}
"""

JS = """
const panes=[...document.querySelectorAll('.pane')],btns=[...document.querySelectorAll('.tabs button')];
function show(id){panes.forEach(p=>p.classList.toggle('on',p.id==='pane-'+id));btns.forEach(b=>b.classList.toggle('on',b.dataset.t===id));history.replaceState(null,'','#'+id)}
btns.forEach(b=>b.onclick=()=>show(b.dataset.t));
document.getElementById('bad').onchange=e=>document.body.classList.toggle('only-bad',e.target.checked);
document.querySelectorAll('.photo img').forEach(i=>i.onclick=()=>i.classList.toggle('zoom'));
document.addEventListener('keydown',e=>{if(e.key==='Escape')document.querySelectorAll('.zoom').forEach(i=>i.classList.remove('zoom'))});
show((location.hash||'#overview').slice(1)||'overview');
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", default=",".join(DEFAULT_RUNS), help="comma-separated run names in data/outputs/")
    ap.add_argument("--pages", default=None, help="comma-separated page stems (default: the held-out pages)")
    ap.add_argument("--out", default=str(ROOT / "data" / "compare.html"))
    ap.add_argument("--no-open", action="store_true", help="do not open the browser")
    args = ap.parse_args()

    pages = args.pages.split(",") if args.pages else default_pages()
    wanted = args.runs.split(",")
    runs = []
    for r in wanted:
        if (OUT_DIR / r).is_dir():
            runs.append(r)
        else:
            print(f"warning: data/outputs/{r}/ not found, leaving that run out")
    if not runs:
        raise SystemExit("No run folders found in data/outputs/. Run ft/evaluate.py or batch.py first.")

    gts, all_evs = {}, {}
    for stem in pages:
        gf = GT_DIR / f"{stem}.json"
        if not gf.exists():
            raise SystemExit(f"No ground truth for {stem} ({gf})")
        gts[stem] = json.loads(gf.read_text(encoding="utf-8"))
        all_evs[stem] = {r: evaluate(gts[stem]["rows"], load_run(r, stem)) for r in runs}

    tabs = '<button data-t="overview">Scoreboard</button>' + "".join(
        f'<button data-t="{esc(s)}">{esc(s)}</button>' for s in pages)
    panes = overview_section(runs, pages, gts, all_evs) + "".join(
        page_section(s, gts[s], runs, all_evs[s]) for s in pages)
    doc = (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
           f'<meta name="viewport" content="width=device-width,initial-scale=1">'
           f'<title>Ledgerly: model comparison</title><style>{CSS}</style></head><body>'
           f'<div class="book"><div class="top"><div><h1>Ledgerly: reading the same khata page</h1>'
           f'<p>Pages the fine-tuned model never saw during training.</p></div>'
           f'<label class="opts"><input type="checkbox" id="bad"> Hide rows every model got right</label></div>'
           f'<div class="tabs">{tabs}</div>{panes}</div><script>{JS}</script></body></html>')
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    print(f"Wrote {out}  ({out.stat().st_size / 1024:.0f} KB, runs: {', '.join(runs)})")
    if not args.no_open:
        webbrowser.open(out.resolve().as_uri())


if __name__ == "__main__":
    main()
