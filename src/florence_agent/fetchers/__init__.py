from pathlib import Path
from typing import Optional

from ..models import Trade


def fetch(source: str, csv_path: Optional[Path] = None) -> tuple[list[Trade], str]:
    """Returns (trades, source_used). 'auto' tries edgeprop → csv → squarefoot → ura."""
    order = {
        "auto": ["edgeprop", "csv", "squarefoot", "ura"],
        "edgeprop": ["edgeprop"],
        "csv": ["csv"],
        "squarefoot": ["squarefoot"],
        "ura": ["ura"],
    }[source]

    last_err: Optional[Exception] = None
    for src in order:
        try:
            if src == "csv":
                if csv_path is None:
                    continue
                from .csv_source import load_csv
                trades = load_csv(csv_path)
            elif src == "edgeprop":
                from .edgeprop import fetch_edgeprop
                trades = fetch_edgeprop()
            elif src == "squarefoot":
                from .squarefoot import fetch_squarefoot
                trades = fetch_squarefoot()
            elif src == "ura":
                from .ura import fetch_ura
                trades = fetch_ura()
            else:
                continue
            if trades:
                return trades, src
        except Exception as e:
            last_err = e
            continue

    if last_err and source != "auto":
        raise last_err
    return [], "none"
