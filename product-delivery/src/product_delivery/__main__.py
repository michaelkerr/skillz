"""Entry point for `python -m product_delivery` and the `product-delivery` console script."""

import sys
from pathlib import Path


def main():
    args = sys.argv[1:]

    if args and args[0] == "setup":
        from .setup import run_setup
        project = Path.cwd()
        if "--dir" in args:
            idx = args.index("--dir")
            if idx + 1 < len(args):
                project = Path(args[idx + 1]).resolve()
        elif "-d" in args:
            idx = args.index("-d")
            if idx + 1 < len(args):
                project = Path(args[idx + 1]).resolve()
        run_setup(project)
        return

    from .server import run
    project_dir = None
    if "--project-dir" in args:
        idx = args.index("--project-dir")
        if idx + 1 < len(args):
            project_dir = Path(args[idx + 1]).resolve()
    run(project_dir)


if __name__ == "__main__":
    main()
