"""Manual generated-order retention cleanup. Dry-run unless --execute is supplied."""

import argparse
import time
from dataclasses import dataclass
from pathlib import Path

from config.settings import get_settings


@dataclass(frozen=True)
class CleanupResult:
    eligible: tuple[Path, ...]
    deleted: tuple[Path, ...]
    skipped: tuple[Path, ...]


def cleanup_generated_orders(
    directory: Path,
    *,
    retention_days: int,
    execute: bool = False,
    template_path: Path | None = None,
    now: float | None = None,
) -> CleanupResult:
    """Select old generated XLSX files and optionally delete them.

    Symlinks, nested paths, non-XLSX files, the configured template, and files newer
    than the retention threshold are always skipped.
    """
    base = directory.resolve()
    template = template_path.resolve() if template_path else None
    cutoff = (now if now is not None else time.time()) - retention_days * 86400
    eligible: list[Path] = []
    deleted: list[Path] = []
    skipped: list[Path] = []
    if not base.is_dir():
        return CleanupResult((), (), ())

    for candidate in base.iterdir():
        try:
            resolved = candidate.resolve()
            safe = (
                not candidate.is_symlink()
                and resolved.parent == base
                and resolved.suffix.lower() == ".xlsx"
                and resolved.is_file()
                and resolved != template
                and resolved.stat().st_mtime < cutoff
            )
            if not safe:
                skipped.append(candidate)
                continue
            eligible.append(candidate)
            if execute:
                resolved.unlink()
                deleted.append(candidate)
        except OSError:
            skipped.append(candidate)
    return CleanupResult(tuple(eligible), tuple(deleted), tuple(skipped))


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Safely clean old generated order workbooks.")
    parser.add_argument("--execute", action="store_true", help="Delete eligible files; default is dry-run.")
    parser.add_argument("--days", type=int, default=settings.generated_file_retention_days)
    args = parser.parse_args()
    if args.days <= 0:
        parser.error("--days must be greater than zero")
    result = cleanup_generated_orders(
        Path(settings.generated_orders_dir),
        retention_days=args.days,
        execute=args.execute,
        template_path=Path(settings.excel_template_path),
    )
    mode = "deleted" if args.execute else "eligible (dry-run)"
    print(f"{mode}: {len(result.deleted) if args.execute else len(result.eligible)}; skipped: {len(result.skipped)}")


if __name__ == "__main__":
    main()
