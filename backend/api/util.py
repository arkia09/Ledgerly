import json
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.http import JsonResponse

TWO_PLACES = Decimal("0.01")


def jr(data, status=200):
    """JSON response that keeps Devanagari readable."""
    return JsonResponse(data, status=status, safe=False,
                        json_dumps_params={"ensure_ascii": False})


def error(code, status=400, **extra):
    return jr({"error": code, **extra}, status=status)


def num(d):
    """Decimal -> JSON number. Money is computed in Decimal; only the output is a float."""
    return None if d is None else float(Decimal(d).quantize(TWO_PLACES))


def iso(d):
    return d.isoformat() if d else None


def read_json(request):
    """Parse the request body. utf-8-sig tolerates the BOM PowerShell 5 likes to add."""
    return json.loads(request.body.decode("utf-8-sig"))


def to_decimal(value, allow_zero=False) -> Decimal | None:
    """Parse a money value (number or string) to Decimal(12,2). None if invalid, negative, or zero
    (unless allow_zero)."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        d = Decimal(str(value).strip().replace(",", ""))
    except InvalidOperation:
        return None
    if not d.is_finite() or d < 0 or (d == 0 and not allow_zero):
        return None
    d = d.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    return d if d < Decimal("10000000000") else None
