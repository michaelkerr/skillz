"""Entry point for `python -m product_delivery` and the `product-delivery` console script."""

import sys
from pathlib import Path

from .server import run


def main():
    project_dir = None
    args = sys.argv[1:]
    if "--project-dir" in args:
        idx = args.index("--project-dir")
        if idx + 1 < len(args):
            project_dir = Path(args[idx + 1]).resolve()
    run(project_dir)


if __name__ == "__main__":
    main()
