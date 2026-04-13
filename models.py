from dataclasses import dataclass
from typing import Optional

@dataclass
class Product:
    id: Optional[int] = None
    name: str = ""
    price: float = 0.0
    barcode: str = ""
    quantity: int = 0

@dataclass
class Sale:
    id: Optional[int] = None
    date: str = ""
    total: float = 0.0
    type: str = "cash"  # cash or debt
    customer: str = ""
