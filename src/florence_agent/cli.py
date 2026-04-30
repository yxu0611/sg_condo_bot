import argparse
import sys
from pathlib import Path

from .fetchers import fetch
from .pairing import classify
from .render import render_html


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="florence-agent")
    p.add_argument(
        "--source",
        choices=["auto", "edgeprop", "csv", "squarefoot", "ura"],
        default="auto",
    )
    p.add_argument("--csv", type=Path, help="Path to URA REALIS CSV export")
    p.add_argument("--out", type=Path, default=Path("florence.html"))
    args = p.parse_args(argv)

    trades, used = fetch(args.source, args.csv)
    if not trades:
        print(f"no trades found from source={args.source}", file=sys.stderr)
        return 2

    print(f"fetched {len(trades)} trades from {used}")
    classified = classify(trades)
    args.out.write_text(render_html(classified, source=used), encoding="utf-8")
    print(f"wrote {args.out} ({args.out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
