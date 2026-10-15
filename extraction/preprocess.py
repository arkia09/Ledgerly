import io
from PIL import Image, ImageOps


def load_image_bytes(path: str, max_side: int = 1280) -> bytes:
    """Fix phone rotation, shrink big photos, boost contrast, return JPEG bytes."""
    img = Image.open(path)
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((max_side, max_side), Image.LANCZOS)
    img = ImageOps.autocontrast(img, cutoff=1)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue()
