import argparse
import json
from pathlib import Path
from typing import Sequence

from app.services.imports import parse_json_rows


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="silver-usage-report")
    subcommands = parser.add_subparsers(dest="command", required=True)

    preview = subcommands.add_parser("preview", help="Preview a normalized JSON report file.")
    preview.add_argument("file", type=Path)

    args = parser.parse_args(argv)
    if args.command == "preview":
        return _preview(args.file)
    return 1


def _preview(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = parse_json_rows(data)
    total_tokens = sum(row.total_tokens or 0 for row in rows)
    print(f"Rows: {len(rows)}")
    print(f"Total tokens: {total_tokens}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
