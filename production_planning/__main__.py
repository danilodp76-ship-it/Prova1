"""Module entry-point for ``python -m production_planning``."""

from .cli import main


if __name__ == "__main__":  # pragma: no cover - executed via -m
    raise SystemExit(main())
