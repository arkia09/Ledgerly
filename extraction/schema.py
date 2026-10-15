from typing import Literal, Optional
from pydantic import BaseModel


class Row(BaseModel):
    # Field order matters: the model writes fields in this order, so it
    # transcribes the row (raw_text) first and then parses it into fields.
    raw_text: str
    date: Optional[str]
    name: Optional[str]
    item: Optional[str]
    amount: Optional[float]
    type: Literal["credit", "payment", "unknown"]
    struck_out: bool
    confidence: float


class Page(BaseModel):
    rows: list[Row]
    page_total: Optional[float]
