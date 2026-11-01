"""Configuration and host scheduling for the Updater (containers/updater)."""
from __future__ import annotations

import getpass
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

UNSAFE = re.compile(r"[\s'\"\\$`#]")
EMAIL = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")


class UpdaterError(Exception):
    pass


def safe(name: str, value: str, *, empty_ok: bool = False) -> str:
    if not value:
        if empty_ok:
            return value
        raise UpdaterError(f"{name}: wartość nie może być pusta.")
    if UNSAFE.search(value) or any(ord(c) < 32 for c in value):
        raise UpdaterError(f"{name}: niedozwolone znaki (spacje, cudzysłowy, \\ $ ` #).")
    return value


def collect(
    old: dict[str, str],
    host: str,
    tls_host: str,
    ask: Callable[[str, str], str],
) -> dict[str, str]:
    """Ask for mail settings; returns .env updates. Blank SMTP host = outbox only."""
    scheme = "https" if tls_host else "http"
    env = {
        "BASE_URL": f"{scheme}://{host}",
        "APP_UID": str(os.getuid()),
        "APP_GID": str(os.getgid()),
    }
    print("\nUpdater wysyła e-mail z linkiem do zatwierdzenia aktualizacji.")
    print("Zostaw SMTP pusty, a wiadomości trafią tylko do updater/state/outbox/.")
    smtp_host = safe("Serwer SMTP", ask("Serwer SMTP (puste = bez wysyłki)", old.get("SMTP_HOST", "")), empty_ok=True)
    env["SMTP_HOST"] = smtp_host
    env["MAIL_TO"] = ""
    env["MAIL_FROM"] = ""
    env["SMTP_USER"] = ""
    env["SMTP_PASSWORD"] = old.get("SMTP_PASSWORD", "")
    env["SMTP_PORT"] = old.get("SMTP_PORT", "587")
    env["SMTP_SECURITY"] = old.get("SMTP_SECURITY", "starttls")
    if not smtp_host:
        env["SMTP_PASSWORD"] = ""
        return env
    to = ask("Adres, na który wysyłać prośby o zatwierdzenie", old.get("MAIL_TO", ""))
    sender = ask("Adres nadawcy (MAIL_FROM)", old.get("MAIL_FROM", "") or to)
    for label, value in (("MAIL_TO", to), ("MAIL_FROM", sender)):
        if not EMAIL.fullmatch(value) or UNSAFE.search(value):
            raise UpdaterError(f"{label}: niepoprawny adres e-mail.")
    env["MAIL_TO"], env["MAIL_FROM"] = to, sender
    security = ask("Szyfrowanie SMTP: starttls lub ssl", env["SMTP_SECURITY"])
    if security not in {"starttls", "ssl"}:
        raise UpdaterError("SMTP_SECURITY musi mieć wartość starttls lub ssl (bez szyfrowania dane logowania nie są wysyłane).")
    env["SMTP_SECURITY"] = security
    default_port = "465" if security == "ssl" and env["SMTP_PORT"] == "587" else env["SMTP_PORT"]
    port = ask("Port SMTP", default_port)
    if not port.isdigit() or not 1 <= int(port) <= 65535:
        raise UpdaterError("Port SMTP musi być liczbą 1-65535.")
    env["SMTP_PORT"] = port
    env["SMTP_USER"] = safe("Login SMTP", ask("Login SMTP (puste = bez logowania)", old.get("SMTP_USER", "")), empty_ok=True)
    if env["SMTP_USER"]:
        typed = getpass.getpass("Hasło SMTP (nie jest wyświetlane; puste = zachowaj obecne): ")
        env["SMTP_PASSWORD"] = safe("Hasło SMTP", typed or env["SMTP_PASSWORD"])
    else:
        env["SMTP_PASSWORD"] = ""
    return env


def host_user() -> str:
    return os.environ.get("SUDO_USER") or getpass.getuser()


def render_units(directory: Path, user: str) -> dict[str, str]:
    """systemd units: apply approved updates every minute, check for updates daily."""
    if not re.fullmatch(r"[a-z_][a-z0-9_-]*", user):
        raise UpdaterError("Nietypowa nazwa użytkownika; nie tworzę jednostek systemd.")
    if UNSAFE.search(str(directory)):
        raise UpdaterError("Ścieżka repozytorium zawiera niedozwolone znaki; nie tworzę jednostek systemd.")
    service = (
        "[Unit]\nDescription=Homelab Updater: {desc}\nAfter=docker.service\nRequires=docker.service\n\n"
        "[Service]\nType=oneshot\nUser={user}\nWorkingDirectory={dir}\n"
        "ExecStart=/usr/bin/python3 {dir}/updater.py {cmd}\n"
    )
    return {
        "homelab-updater-apply.service": service.format(desc="apply approved updates", user=user, dir=directory, cmd="apply"),
        "homelab-updater-apply.timer": "[Unit]\nDescription=Homelab Updater apply (every minute)\n\n[Timer]\nOnBootSec=2min\nOnUnitActiveSec=1min\n\n[Install]\nWantedBy=timers.target\n",
        "homelab-updater-check.service": service.format(desc="check for updates", user=user, dir=directory, cmd="check"),
        "homelab-updater-check.timer": "[Unit]\nDescription=Homelab Updater check (daily)\n\n[Timer]\nOnCalendar=*-*-* 04:30:00\nRandomizedDelaySec=15min\nPersistent=true\n\n[Install]\nWantedBy=timers.target\n",
    }


def install_timers(directory: Path, user: str, privileged: Callable[..., subprocess.CompletedProcess[str]]) -> None:
    for name, text in render_units(directory, user).items():
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as handle:
            handle.write(text)
            temp = Path(handle.name)
        try:
            privileged(["install", "-m", "0644", "-o", "root", "-g", "root", str(temp), f"/etc/systemd/system/{name}"])
        finally:
            temp.unlink(missing_ok=True)
    privileged(["systemctl", "daemon-reload"])
    privileged(["systemctl", "enable", "--now", "homelab-updater-apply.timer", "homelab-updater-check.timer"])
