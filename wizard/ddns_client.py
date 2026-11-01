"""Optional installation of a DDNS client running on the host (not in Docker)."""
from __future__ import annotations

import getpass
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

CLIENTS = {
    "ddclient": "ddclient (pakiet systemowy)",
    "inadyn": "inadyn (pakiet systemowy)",
}
PROVIDERS = {
    "duckdns": "DuckDNS",
    "cloudflare": "Cloudflare (token API: Zone:DNS:Edit, Zone:Zone:Read)",
    "noip": "No-IP",
}
SAFE_VALUE = re.compile(r"[^\s'\"\\#,{}]+")


class DdnsError(Exception):
    pass


def validate_secret(name: str, value: str) -> str:
    if not value or not SAFE_VALUE.fullmatch(value):
        raise DdnsError(f"{name}: pusta wartość albo niedozwolone znaki (spacje, cudzysłowy, \\ # , {{ }}).")
    return value


def duckdns_labels(hostnames: list[str]) -> list[str]:
    labels = []
    for hostname in hostnames:
        if not hostname.endswith(".duckdns.org"):
            raise DdnsError(f"{hostname} nie jest nazwą DuckDNS (oczekiwano *.duckdns.org).")
        labels.append(hostname[: -len(".duckdns.org")])
    return labels


def render_ddclient(provider: str, hostnames: list[str], creds: dict[str, str]) -> str:
    lines = ["daemon=300", "syslog=yes", "ssl=yes", "use=web"]
    if provider == "duckdns":
        lines += ["protocol=duckdns", f"password={validate_secret('Token', creds['password'])}"]
        hosts = duckdns_labels(hostnames)
    elif provider == "cloudflare":
        lines += [
            "protocol=cloudflare",
            f"zone={validate_secret('Strefa', creds['zone'])}",
            f"password={validate_secret('Token', creds['password'])}",
        ]
        hosts = hostnames
    elif provider == "noip":
        lines += [
            "protocol=noip",
            "server=dynupdate.no-ip.com",
            f"login={validate_secret('Login', creds['login'])}",
            f"password={validate_secret('Hasło', creds['password'])}",
        ]
        hosts = hostnames
    else:
        raise DdnsError(f"Nieobsługiwany dostawca DDNS: {provider}")
    return "\n".join(lines + [",".join(hosts)]) + "\n"


def render_inadyn(provider: str, hostnames: list[str], creds: dict[str, str]) -> str:
    hosts = "{ " + ", ".join(f'"{h}"' for h in hostnames) + " }"
    if provider == "duckdns":
        duckdns_labels(hostnames)
        body = (
            f"    username = {validate_secret('Token', creds['password'])}\n"
            "    password = noPasswordForDuckdns\n"
        )
        name = "duckdns.org"
    elif provider == "cloudflare":
        body = (
            f"    username = {validate_secret('Strefa', creds['zone'])}\n"
            f"    password = {validate_secret('Token', creds['password'])}\n"
        )
        name = "cloudflare.com"
    elif provider == "noip":
        body = (
            f"    username = {validate_secret('Login', creds['login'])}\n"
            f"    password = {validate_secret('Hasło', creds['password'])}\n"
        )
        name = "no-ip.com"
    else:
        raise DdnsError(f"Nieobsługiwany dostawca DDNS: {provider}")
    return f"period = 300\n\nprovider {name} {{\n{body}    hostname = {hosts}\n}}\n"


def config_path(client: str, distro: str) -> Path:
    if client == "ddclient":
        return Path("/etc/ddclient/ddclient.conf" if distro == "fedora" else "/etc/ddclient.conf")
    return Path("/etc/inadyn.conf")


def install_client(
    client: str,
    distro: str,
    privileged: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    if distro in {"ubuntu", "debian"}:
        privileged(["env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", "-y", client])
    elif distro == "fedora":
        privileged(["dnf", "install", "-y", client])
    else:
        raise DdnsError("Instalacja klienta DDNS jest obsługiwana na Ubuntu, Debianie i Fedorze.")


def write_config(path: Path, text: str, privileged: Callable[..., subprocess.CompletedProcess[str]]) -> None:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as handle:
        os.fchmod(handle.fileno(), 0o600)
        handle.write(text)
        temp = Path(handle.name)
    try:
        privileged(["install", "-d", "-m", "0755", str(path.parent)])
        privileged(["install", "-m", "0600", "-o", "root", "-g", "root", str(temp), str(path)])
    finally:
        temp.unlink(missing_ok=True)


def collect(
    hostnames: list[str],
    ask: Callable[[str, str], str],
) -> tuple[str, str, dict[str, str]] | None:
    print("\nKlient DDNS na hoście (opcjonalnie; kreator nie instaluje DDNS w Dockerze):")
    print("  1. ddclient\n  2. inadyn\n  3. Pomiń (DDNS skonfigurowany w routerze/u dostawcy)")
    choice = ask("Wybierz 1-3", "3")
    if choice == "3":
        return None
    if choice not in {"1", "2"}:
        raise DdnsError("Nieprawidłowy wybór klienta DDNS.")
    client = "ddclient" if choice == "1" else "inadyn"
    names = list(PROVIDERS)
    for number, name in enumerate(names, 1):
        print(f"  {number}. {PROVIDERS[name]}")
    index = ask(f"Dostawca DDNS 1-{len(names)}", "1")
    if not index.isdigit() or not 1 <= int(index) <= len(names):
        raise DdnsError("Nieprawidłowy wybór dostawcy DDNS.")
    provider = names[int(index) - 1]
    creds: dict[str, str] = {}
    if provider == "cloudflare":
        creds["zone"] = ask("Strefa Cloudflare (domena bazowa)", "")
        creds["password"] = getpass.getpass("Token API Cloudflare (nie jest wyświetlany): ")
    elif provider == "duckdns":
        creds["password"] = getpass.getpass("Token DuckDNS (nie jest wyświetlany): ")
    else:
        creds["login"] = ask("Login No-IP", "")
        creds["password"] = getpass.getpass("Hasło/klucz DDNS No-IP (nie jest wyświetlane): ")
    if not hostnames:
        raise DdnsError("Brak hostnames do aktualizacji przez klienta DDNS.")
    render(client, provider, hostnames, creds)  # validate before touching the system
    return client, provider, creds


def render(client: str, provider: str, hostnames: list[str], creds: dict[str, str]) -> str:
    renderer = render_ddclient if client == "ddclient" else render_inadyn
    return renderer(provider, sorted(set(hostnames)), creds)


def apply(
    client: str,
    provider: str,
    hostnames: list[str],
    creds: dict[str, str],
    distro: str,
    privileged: Callable[..., subprocess.CompletedProcess[str]],
) -> Path:
    text = render(client, provider, hostnames, creds)
    install_client(client, distro, privileged)
    path = config_path(client, distro)
    write_config(path, text, privileged)
    privileged(["systemctl", "enable", "--now", client])
    privileged(["systemctl", "restart", client])
    return path
