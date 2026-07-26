"""Production-safe startup and readiness checks. Never writes to the source template."""

import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from config.settings import Settings
from database.session import check_database


class StartupValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ComponentStatus:
    database: str
    template: str
    generated_orders: str

    @property
    def ready(self) -> bool:
        return all(value == "ok" for value in (self.database, self.template, self.generated_orders))


def _is_readable_file(path: Path) -> bool:
    return path.is_file() and os.access(path, os.R_OK)


def _directory_writable(path: Path, *, create: bool) -> bool:
    probe: Path | None = None
    try:
        if create:
            path.mkdir(parents=True, exist_ok=True)
        if not path.is_dir() or not os.access(path, os.W_OK):
            return False
        probe = path / f".readiness-{uuid.uuid4().hex}"
        with probe.open("x", encoding="utf-8") as handle:
            handle.write("")
        return True
    except OSError:
        return False
    finally:
        if probe is not None:
            try:
                probe.unlink(missing_ok=True)
            except OSError:
                pass


def _database_parent_writable(database_url: str, *, create: bool) -> bool:
    if not database_url.startswith("sqlite:///") or database_url == "sqlite:///:memory:":
        return True
    database_path = Path(database_url.removeprefix("sqlite:///"))
    parent = database_path.resolve().parent
    try:
        if create:
            parent.mkdir(parents=True, exist_ok=True)
        return parent.is_dir() and os.access(parent, os.W_OK)
    except OSError:
        return False


def readiness_status(settings: Settings, *, create_directories: bool = False) -> ComponentStatus:
    template = "ok" if _is_readable_file(Path(settings.excel_template_path)) else "unavailable"
    generated = (
        "ok"
        if _directory_writable(Path(settings.generated_orders_dir), create=create_directories)
        else "unavailable"
    )
    database = "unavailable"
    if _database_parent_writable(settings.database_url, create=create_directories):
        try:
            check_database(settings.database_url)
            database = "ok"
        except Exception:
            database = "unavailable"
    return ComponentStatus(database=database, template=template, generated_orders=generated)


def validate_startup(settings: Settings) -> ComponentStatus:
    if settings.email_enabled:
        from services.email_config_service import EmailConfigurationError, validate_email_configuration

        try:
            validate_email_configuration(settings)
        except EmailConfigurationError as exc:
            raise StartupValidationError("email configuration is incomplete") from exc
    status = readiness_status(settings, create_directories=True)
    if not status.ready:
        failed = [
            name for name, value in (
                ("database", status.database),
                ("template", status.template),
                ("generated_orders", status.generated_orders),
            ) if value != "ok"
        ]
        raise StartupValidationError(f"startup validation failed for: {', '.join(failed)}")
    return status
