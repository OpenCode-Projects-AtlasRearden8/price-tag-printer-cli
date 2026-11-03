"""Label model shared by the parsers and exporters."""

from __future__ import annotations

from dataclasses import dataclass



@dataclass
class Size:
    """A physical label size in inches."""

    width: float
    height: float

    def __post_init__(self) -> None:
        if not (0 < self.width <= 100 and 0 < self.height <= 100):
            raise ValueError(f"Label size out of range: {self.width}x{self.height}")


@dataclass
class Label:
    """One price tag to render."""

    product: str
    price: str
    description: str = ""
    sale_price: str = ""
    strike: bool = False
    barcode: str = ""
    copies: int = 1

    @property
    def on_sale(self) -> bool:
        return bool(self.sale_price.strip())

    @property
    def has_barcode(self) -> bool:
        return bool(self.barcode.strip())
