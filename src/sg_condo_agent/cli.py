import argparse
import sys
from pathlib import Path

from .condos import get, list_keys
from .fetchers import fetch
from .pairing import classify
from .render import render_html


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="sg-condo-agent",
        description="Fetch SG condo transactions and emit a static HTML report.",
    )
    p.add_argument(
        "--condo",
        required=True,
        help=(
            "Condo to query. Either a registered key "
            f"({', '.join(list_keys()) or '<none yet>'}) or a free-form "
            "project name (URA / CSV sources will still work)."
        ),
    )
    p.add_argument(
        "--source",
        choices=["auto", "edgeprop", "csv", "squarefoot", "ura"],
        default="auto",
    )
    p.add_argument("--csv", type=Path, help="Path to URA REALIS CSV export")
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output HTML path. Defaults to <condo-key>.html.",
    )
    args = p.parse_args(argv)

    condo = get(args.condo)
    out_path = args.out or Path(f"{condo.key}.html")

    trades, used = fetch(condo, args.source, args.csv)
    if not trades:
        print(
            f"no trades found for condo={condo.name!r} from source={args.source}",
            file=sys.stderr,
        )
        return 2

    print(f"fetched {len(trades)} trades for {condo.name} from {used}")
    classified = classify(trades)
    out_path.write_text(render_html(classified, source=used, condo=condo), encoding="utf-8")
    print(f"wrote {out_path} ({out_path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
