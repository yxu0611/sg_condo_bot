import csv
from datetime import date, datetime
from pathlib import Path

from ..models import Trade


def _parse_floor(level: str) -> str:
    return level.strip().replace(" to ", "-").replace(" TO ", "-")


def _parse_date(s: str) -> date:
    return datetime.strptime(s.strip(), "%b-%y").date()


def _parse_price(s: str) -> int:
    return int(s.replace(",", "").replace("$", "").strip())


def _parse_area_sqft(s: str) -> int:
    # URA exports area as a decimal string like "764.24"
    return int(round(float(s.replace(",", "").strip())))


def _infer_unit_type(area_sqft: int) -> str:
    if area_sqft < 550:
        return "1BR"
    if area_sqft < 800:
        return "2BR"
    if area_sqft < 1100:
        return "3BR"
    return "4BR+"


def _get(row: dict, *keys: str) -> str:
    for k in keys:
        if k in row and row[k] is not None:
            return row[k]
    raise KeyError(f"none of {keys} in row")


def load_csv(path: Path | str) -> list[Trade]:
    path = Path(path)
    out: list[Trade] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            project = _get(row, "Project Name").upper()
            if "FLORENCE" not in project:
                continue
            area = _parse_area_sqft(_get(row, "Area (SQFT)", "Area (Sqft)"))
            price = _parse_price(_get(row, "Transacted Price ($)", "Price ($)"))
            sale_date = _parse_date(_get(row, "Sale Date", "Date of Sale"))
            floor = _parse_floor(_get(row, "Floor Level"))
            tenure = _get(row, "Tenure").strip()
            sale_type = _get(row, "Type of Sale").strip()
            out.append(
                Trade(
                    contract_date=sale_date,
                    block="-",
                    floor_range=floor,
                    area_sqft=area,
                    unit_type=_infer_unit_type(area),
                    price_sgd=price,
                    tenure=tenure,
                    sale_type=sale_type,
                )
            )
    return out
