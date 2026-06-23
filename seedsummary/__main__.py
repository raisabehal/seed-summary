"""CLI: `python -m seedsummary run [--no-email] [--verbose]`."""
from __future__ import annotations

import argparse
import json
import logging
import sys


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="seedsummary", description="Weekly funded-company scanner")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="Run the weekly scan")
    run_p.add_argument("--no-email", action="store_true", help="Build outputs but don't send email")
    run_p.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if getattr(args, "verbose", False) else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.cmd == "run":
        from . import pipeline
        result = pipeline.run(send=not args.no_email)
        print(json.dumps(result, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
