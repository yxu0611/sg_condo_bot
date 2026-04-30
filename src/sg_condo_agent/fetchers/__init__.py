from pathlib import Path
from typing import Optional

from ..condos import Condo
from ..models import Trade


def fetch(
    condo: Condo,
    source: str,
    csv_path: Optional[Path] = None,
) -> tuple[list[Trade], str]:
    """Returns (trades, source_used). 'auto' tries edgeprop → csv → squarefoot → ura.

    Sources that the condo lacks configuration for (no edgeprop_asset_id, no
    squarefoot_slug) are skipped silently in 'auto' mode and raise a clear
    error in pinned mode.
    """
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
                trades = load_csv(csv_path, condo)
            elif src == "edgeprop":
                if source == "auto" and not condo.edgeprop_asset_id:
                    continue
                from .edgeprop import fetch_edgeprop
                trades = fetch_edgeprop(condo)
            elif src == "squarefoot":
                if source == "auto" and not condo.squarefoot_slug:
                    continue
                from .squarefoot import fetch_squarefoot
                trades = fetch_squarefoot(condo)
            elif src == "ura":
                from .ura import fetch_ura
                trades = fetch_ura(condo)
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
