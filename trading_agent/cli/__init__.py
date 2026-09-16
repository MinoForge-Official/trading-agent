"""CLI interface package."""

__all__ = ["main"]


def main():
    from .main import main as _main
    return _main()