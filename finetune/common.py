"""Shared helpers for the Tinker fine-tuning pipeline (no Tinker import here, so it is testable offline)."""
import io
import json
import random
import re
import sys
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "data" / "pages"
GROUND_TRUTH = ROOT / "data" / "ground_truth"
OUT_ROOT = ROOT / "data" / "outputs"
WORK = ROOT / "data" / "finetune"          # prepared dataset + run info (gitignored with data/)

# Scoring/Schema live in extraction/ with flat imports; put it first on sys.path
# (PyPI has an unrelated "schema" package that would otherwise win).
sys.path.insert(0, str(ROOT / "extraction"))
from schema import Page  # noqa: E402

# Cheap, capable and confirmed to take images in the Tinker cookbook (MoE: cost follows the ~3B active params).
DEFAULT_MODEL = "Qwen/Qwen3-VL-30B-A3B-Instruct"
MAX_IMAGE_SIDE = 1024
FIELDS = ("date", "name", "item", "amount", "type", "struck_out")

PROMPT = """Read this photographed page of a handwritten shop credit ledger (khata).
Text may be English, Hindi (Devanagari) or a mix. Columns, left to right:
date | customer name | item(s) | Udhaar | Jama.
An amount in Udhaar (goods given on credit) means type "credit"; an amount in Jama
(money paid back) means type "payment". Use "unknown" only if you cannot tell.

Rules:
- Copy names and dates exactly as written. Do not translate, correct or complete them.
- Amounts are plain numbers in Western digits, no symbols.
- struck_out is true if a line is drawn through the row. Still include the row.
- item is null when no item is written.
- Return rows in page order. Ignore headers and doodles.

Reply with JSON only, in exactly this shape:
{"rows":[{"date":"21/09","name":"Ramesh","item":"atta 5kg","amount":240,"type":"credit","struck_out":false}],"page_total":null}"""


def target_json(rows: list[dict], page_total=None) -> str:
    """The exact text the model is trained to produce for a page."""
    clean = [{k: r.get(k) for k in FIELDS} for r in rows]
    for r in clean:
        r["struck_out"] = bool(r["struck_out"])
        if r["amount"] is not None:
            a = float(r["amount"])
            r["amount"] = int(a) if a == int(a) else a
    return json.dumps({"rows": clean, "page_total": page_total}, ensure_ascii=False, separators=(",", ":"))


def parse_output(text: str) -> dict:
    """Model text -> dict matching extraction.schema.Page (raw_text/confidence are filled in).

    Raises ValueError with the problem if the text is not valid ledger JSON.
    """
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    start, end = t.find("{"), t.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object found")
    data = json.loads(t[start:end + 1])
    rows = []
    for r in data.get("rows", []):
        rows.append({
            "raw_text": " ".join(str(r.get(k)) for k in ("date", "name", "item", "amount") if r.get(k) is not None),
            "date": r.get("date"), "name": r.get("name"), "item": r.get("item"),
            "amount": r.get("amount"), "type": r.get("type", "unknown"),
            "struck_out": bool(r.get("struck_out", False)),
            "confidence": 1.0,   # the tuned model does not report confidence
        })
    return Page.model_validate({"rows": rows, "page_total": data.get("page_total")}).model_dump()


def load_image(path: Path, max_side: int = MAX_IMAGE_SIDE) -> Image.Image:
    """Same preprocessing as the app: fix phone rotation, shrink, boost contrast."""
    img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    img.thumbnail((max_side, max_side), Image.LANCZOS)
    return ImageOps.autocontrast(img, cutoff=1)


def augment(img: Image.Image, seed: int) -> Image.Image:
    """Mimic different phone photos of the same page: tilt, crop, light, blur, JPEG noise.
    No flips (that would mirror the handwriting)."""
    rng = random.Random(seed)
    w, h = img.size
    img = img.rotate(rng.uniform(-3, 3), resample=Image.BICUBIC, fillcolor=(235, 235, 235))
    s = rng.uniform(0.92, 1.0)
    cw, ch = int(w * s), int(h * s)
    x, y = rng.randint(0, w - cw), rng.randint(0, h - ch)
    img = img.crop((x, y, x + cw, y + ch))
    img = ImageEnhance.Brightness(img).enhance(rng.uniform(0.8, 1.2))
    img = ImageEnhance.Contrast(img).enhance(rng.uniform(0.85, 1.25))
    if rng.random() < 0.3:
        img = img.filter(ImageFilter.GaussianBlur(rng.uniform(0.4, 1.0)))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=rng.randint(60, 90))
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")


def ground_truth_pages() -> list[str]:
    return sorted(p.stem for p in GROUND_TRUTH.glob("*.json") if not p.name.startswith("_"))


def find_image(stem: str) -> Path | None:
    return next((p for ext in (".jpg", ".jpeg", ".png", ".webp")
                 if (p := PAGES / f"{stem}{ext}").exists()), None)


def renderer_for(model: str):
    """Tokenizer + image-capable renderer for a model, using the cookbook's recommended name."""
    from tinker_cookbook import model_info, renderers
    from tinker_cookbook.image_processing_utils import get_image_processor
    from tinker_cookbook.tokenizer_utils import get_tokenizer

    names = model_info.get_recommended_renderer_names(model)
    name = next((n for n in names if n.endswith("disable_thinking")), names[0])  # no <think> tokens: cheaper, easier to parse
    renderer = renderers.get_renderer(name, get_tokenizer(model), image_processor=get_image_processor(model))
    return renderer, name


def user_message(image: Image.Image):
    from tinker_cookbook.renderers import ImagePart, Message, TextPart
    return Message(role="user", content=[ImagePart(type="image", image=image), TextPart(type="text", text=PROMPT)])
