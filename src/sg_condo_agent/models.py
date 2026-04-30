from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class Trade:
    contract_date: date
    block: str
    floor_range: str
    area_sqft: int
    unit_type: str
    price_sgd: int
    tenure: str
    sale_type: str
    unit_number: Optional[str] = None  # e.g. "14-38"; None when source lacks it

    @property
    def psf(self) -> float:
        return self.price_sgd / self.area_sqft if self.area_sqft else 0.0

    @property
    def pair_key(self) -> tuple:
        # When the data source provides a real unit number (EdgeProp), pair
        # by that — same physical unit. Otherwise fall back to the URA-CSV
        # heuristic of (block, floor band, area, unit type).
        if self.unit_number:
            return ("unit", self.block, self.unit_number)
        return ("band", self.block, self.floor_range, self.area_sqft, self.unit_type)
