#!/usr/bin/env python3
"""Interactive, additive Homelab Compose installer."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import ddns_client


ROOT = Path(__file__).resolve().parents[1]
CONTAINERS = ROOT / "containers"
STATE_FILE = ROOT / ".homelab-state.json"

SERVICES = {
    "nextcloud": ("Nextcloud + PostgreSQL + Redis", True, ()),
    "immich": ("Immich (zdjęcia)", True, ()),
    "home-assistant": ("Home Assistant", False, ()),
    "mqtt": ("Mosquitto MQTT", False, ()),
    "zigbee2mqtt": ("Zigbee2MQTT", True, ("mqtt",)),
    "wordpress": ("WordPress + MySQL", True, ()),
    "django": ("Django (alternatywa dla WordPressa)", True, ()),
    "jellyfin": ("Jellyfin", True, ()),
    "euro-office": ("Euro-Office dla Nextcloud", True, ("nextcloud",)),
    "minecraft": ("Minecraft Java", False, ()),
    "samba": ("Samba SMB", False, ()),
}
WEB_ENV = {
    "nextcloud": ("NEXTCLOUD_HOST", "NEXTCLOUD_TLS_HOST"),
    "immich": ("IMMICH_HOST", "IMMICH_TLS_HOST"),
    "zigbee2mqtt": ("ZIGBEE2MQTT_HOST", "ZIGBEE2MQTT_TLS_HOST"),
    "wordpress": ("WORDPRESS_HOST", "WORDPRESS_TLS_HOST"),
    "django": ("DJANGO_HOST", "DJANGO_TLS_HOST"),
    "jellyfin": ("JELLYFIN_HOST", "JELLYFIN_TLS_HOST"),
    "euro-office": ("EURO_OFFICE_HOST", "EURO_OFFICE_TLS_HOST"),
}
START_ORDER = (
    "nginx-proxy",
    "mqtt",
    "home-assistant",
    "nextcloud",
    "immich",
    "wordpress",
    "django",
    "jellyfin",
    "euro-office",
    "zigbee2mqtt",
    "minecraft",
    "samba",
)


class WizardError(Exception):
    pass


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or default


def confirm(prompt: str, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    value = input(f"{prompt} ({hint}): ").strip().lower()
    if not value:
        return default
    return value in {"y", "yes", "t", "tak"}


def read_os_release() -> dict[str, str]:
    result: dict[str, str] = {}
    path = Path("/etc/os-release")
    if not path.exists():
        return result
    for line in path.read_text().splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        result[key] = value.strip().strip('"').strip("'")
    return result


def run(command: list[str], *, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
    print("+ " + shlex.join(command))
    return subprocess.run(
        command,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def privileged(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    prefix = [] if os.geteuid() == 0 else ["sudo"]
    return run([*prefix, *command], check=check)


def install_packages(os_info: dict[str, str]) -> None:
    distro = os_info.get("ID", "").lower()
    if distro in {"ubuntu", "debian"}:
        repo_distro = distro
        codename = (
            os_info.get("UBUNTU_CODENAME")
            or os_info.get("VERSION_CODENAME")
        )
        if not codename:
            raise WizardError("Nie udało się odczytać nazwy wydania systemu.")
        privileged(["apt-get", "update"])
        privileged(["apt-get", "install", "-y", "ca-certificates", "curl", "gnupg", "ufw", "cockpit"])
        privileged(["install", "-m", "0755", "-d", "/etc/apt/keyrings"])
        privileged([
            "curl", "-fsSL", f"https://download.docker.com/linux/{repo_distro}/gpg",
            "-o", "/etc/apt/keyrings/docker.asc",
        ])
        privileged(["chmod", "a+r", "/etc/apt/keyrings/docker.asc"])
        arch = subprocess.check_output(["dpkg", "--print-architecture"], text=True).strip()
        source = (
            "Types: deb\n"
            f"URIs: https://download.docker.com/linux/{repo_distro}\n"
            f"Suites: {codename}\n"
            "Components: stable\n"
            f"Architectures: {arch}\n"
            "Signed-By: /etc/apt/keyrings/docker.asc\n"
        )
        source_path = Path("/etc/apt/sources.list.d/docker.sources")
        if source_path.exists() and not confirm(f"Nadpisać {source_path}?", False):
            raise WizardError("Przerwano, aby nie nadpisać istniejącej konfiguracji repozytorium.")
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as source_file:
            source_file.write(source)
            source_temp = Path(source_file.name)
        try:
            privileged(["install", "-m", "0644", str(source_temp), str(source_path)])
        finally:
            source_temp.unlink(missing_ok=True)
        privileged(["apt-get", "update"])
        privileged([
            "apt-get", "install", "-y", "docker-ce", "docker-ce-cli", "containerd.io",
            "docker-buildx-plugin", "docker-compose-plugin",
        ])
        privileged(["systemctl", "enable", "--now", "docker"])
        privileged(["systemctl", "enable", "--now", "cockpit.socket"])
        return

    if distro == "fedora":
        privileged(["dnf", "install", "-y", "dnf-plugins-core", "cockpit", "firewalld", "curl"])
        repo = "https://download.docker.com/linux/fedora/docker-ce.repo"
        privileged(["dnf", "config-manager", "addrepo", f"--from-repofile={repo}"])
        privileged([
            "dnf", "install", "-y", "docker-ce", "docker-ce-cli", "containerd.io",
            "docker-buildx-plugin", "docker-compose-plugin",
        ])
        privileged(["systemctl", "enable", "--now", "docker"])
        privileged(["systemctl", "enable", "--now", "cockpit.socket"])
        privileged(["systemctl", "enable", "--now", "firewalld"])
        return

    raise WizardError(
        f"Automatyczna instalacja obsługuje Ubuntu, Debian i Fedora; wykryto: {distro or 'nieznany system'}. "
        "Zainstaluj Docker Engine, Compose v2 i Cockpit zgodnie z dokumentacją dystrybucji, "
        "a następnie ponownie uruchom kreator."
    )


def docker_prefix() -> list[str]:
    if os.geteuid() == 0:
        return ["docker"]
    test = subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if test.returncode == 0:
        return ["docker"]
    if shutil.which("sudo"):
        return ["sudo", "docker"]
    raise WizardError("Docker wymaga uprawnień. Uruchom kreator przez sudo albo skonfiguruj dostęp do demona.")


def detect_lan_address() -> str:
    if not shutil.which("ip"):
        return "127.0.0.1"
    result = subprocess.run(
        ["ip", "-o", "-4", "route", "get", "1.1.1.1"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    match = re.search(r"\bsrc\s+(\d{1,3}(?:\.\d{1,3}){3})", result.stdout)
    return match.group(1) if match else "127.0.0.1"


def select_services(already: set[str]) -> set[str]:
    print("\nDostępne usługi:")
    names = list(SERVICES)
    for number, name in enumerate(names, 1):
        state = " [już skonfigurowano]" if name in already else ""
        print(f"  {number}. {name} — {SERVICES[name][0]}{state}")
    raw = ask("Podaj numery lub nazwy oddzielone przecinkami; Enter = tylko nowe")
    if not raw:
        selected = set(names) - already
    elif raw.lower() in {"all", "wszystkie"}:
        selected = set(names)
    else:
        selected = set()
        for token in raw.split(","):
            item = token.strip()
            if item.isdigit() and 1 <= int(item) <= len(names):
                selected.add(names[int(item) - 1])
            elif item in SERVICES:
                selected.add(item)
            else:
                raise WizardError(f"Nieznana usługa lub numer: {item}")
    if not selected and raw:
        raise WizardError("Nie wybrano nowych usług.")
    for service in tuple(selected):
        selected.update(SERVICES[service][2])
    return selected


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def write_env(path: Path, updates: dict[str, str]) -> None:
    template = path.with_name(".env.example")
    lines = template.read_text().splitlines() if template.exists() else []
    values = read_env(path) if path.exists() else {}
    if not path.exists():
        values = read_env(template)
    values.update(updates)
    for key, value in list(values.items()):
        if value.startswith("replace-with-") and key.endswith(("PASSWORD", "SECRET", "TOKEN")):
            values[key] = secrets.token_hex(32)
    output: list[str] = []
    written: set[str] = set()
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in values:
                output.append(f"{key}={values[key]}")
                written.add(key)
                continue
        output.append(line)
    for key, value in values.items():
        if key not in written:
            output.append(f"{key}={value}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".env.tmp")
    temp.write_text("\n".join(output).rstrip() + "\n")
    os.chmod(temp, 0o600)
    temp.replace(path)


def validate_domain(value: str) -> bool:
    if len(value) > 253 or not value or value.endswith("."):
        return False
    labels = value.split(".")
    return len(labels) >= 2 and all(
        1 <= len(label) <= 63
        and re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?", label)
        for label in labels
    )


def ask_domain(prompt: str, default: str) -> str:
    while True:
        value = ask(prompt, default).lower()
        if validate_domain(value):
            return value
        print("Podaj poprawną nazwę DNS, np. cloud.example.org.")


def collect_network(selected: set[str], old_values: dict[str, dict[str, str]]) -> tuple[dict[str, dict[str, str]], dict[str, str], str]:
    web_services = sorted(selected.intersection(WEB_ENV))
    public_services = [name for name in web_services if name != "zigbee2mqtt"]
    network_env: dict[str, dict[str, str]] = {}
    ddns_env: dict[str, str] = {}
    mode = "local"
    lan_ip = detect_lan_address()
    old_proxy = read_env(CONTAINERS / "nginx-proxy" / ".env")
    if public_services:
        print("\nDostęp sieciowy dla usług WWW:")
        print("  1. LAN/VPN (lokalna domena, bez certyfikatu publicznego)")
        print("  2. Publiczne IP stałe (ręczne rekordy DNS)")
        print("  3. Dynamiczne IP z DDNS (opcjonalny klient na hoście: ddclient/inadyn)")
        mode_default = {
            "local": "1",
            "static": "2",
            "ddns": "3",
        }.get(
            old_proxy.get("NETWORK_MODE", ""),
            "1",
        )
        choice = ask("Wybierz 1-3", mode_default)
        mode = {"1": "local", "2": "static", "3": "ddns"}.get(choice, "")
        if not mode:
            raise WizardError("Nieprawidłowy wybór dostępu sieciowego.")

    base_domain = ""
    if mode == "local" and web_services:
        base_domain = ask_domain(
            "Lokalna strefa DNS (skonfiguruj ją w swoim DNS/routerze)",
            old_proxy.get("BASE_DOMAIN", "home.arpa"),
        )
    elif mode == "static":
        base_domain = ask_domain("Twoja domena bazowa", old_proxy.get("BASE_DOMAIN", "example.org"))
        while True:
            public_ip = ask("Stały publiczny IPv4", old_proxy.get("STATIC_PUBLIC_IPV4", ""))
            try:
                address = ipaddress.ip_address(public_ip)
                if address.version == 4 and address.is_global:
                    ddns_env["STATIC_PUBLIC_IPV4"] = public_ip
                    break
            except ValueError:
                pass
            print("Wpisz globalny, publiczny IPv4 (nie adres prywatny/LAN).")
    elif mode == "ddns":
        base_domain = ask_domain(
            "Domena lub nazwa z Twojego dostawcy DDNS",
            old_proxy.get("BASE_DOMAIN", "example.org"),
        )
        print("Klienta DDNS możesz zainstalować na końcu albo pominąć, jeśli DDNS działa w routerze (zob. docs/ddns.md).")

    bind_ip = old_proxy.get("PROXY_BIND_ADDRESS", lan_ip)
    if web_services or "samba" in selected:
        bind_ip = ask("Adres IP interfejsu LAN serwera dla proxy/SMB", lan_ip)
        try:
            if ipaddress.ip_address(bind_ip).version != 4:
                raise ValueError("The proxy compose template expects an IPv4 bind address.")
        except ValueError as exc:
            raise WizardError("Podaj poprawny adres IPv4 interfejsu LAN.") from exc

    for service in web_services:
        host_key, tls_key = WEB_ENV[service]
        old = old_values.get(service, {})
        current = old.get(host_key, "")
        if service == "zigbee2mqtt" and mode != "local":
            network_env[service] = {host_key: "", tls_key: "", "LETSENCRYPT_EMAIL": ""}
            continue
        if mode == "local":
            default = current or f"{service.replace('-', '')}.{base_domain}"
            hostname = ask_domain(f"Hostname dla {service} (lokalny DNS)", default)
            tls_hostname = ""
        elif mode == "static":
            default = current or f"{service.replace('-', '')}.{base_domain}"
            hostname = ask_domain(f"Publiczny hostname dla {service}", default)
            tls_hostname = hostname
            print(f"  DNS: ustaw rekord A {hostname} → {ddns_env['STATIC_PUBLIC_IPV4']}.")
        else:
            default = current or f"{service.replace('-', '')}.{base_domain}"
            hostname = ask_domain(f"Publiczny hostname DDNS dla {service}", default)
            tls_hostname = hostname

        updates = {host_key: hostname, tls_key: tls_hostname, "LETSENCRYPT_EMAIL": ""}
        network_env.setdefault(service, {}).update(updates)
        if service == "nextcloud":
            old_trusted = old.get("NEXTCLOUD_TRUSTED_DOMAINS", "localhost 127.0.0.1")
            trusted = set(old_trusted.split())
            trusted.add(hostname)
            network_env[service]["NEXTCLOUD_TRUSTED_DOMAINS"] = " ".join(sorted(trusted))

    if mode in {"static", "ddns"} and public_services:
        email = ask("Adres e-mail dla Let's Encrypt", old_proxy.get("LETSENCRYPT_EMAIL", ""))
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise WizardError("Podaj poprawny adres e-mail.")
        for service in public_services:
            network_env[service]["LETSENCRYPT_EMAIL"] = email

    proxy_env = network_env.setdefault("nginx-proxy", {})
    proxy_env.update({
        "PROXY_BIND_ADDRESS": bind_ip,
        "NETWORK_MODE": mode,
        "BASE_DOMAIN": base_domain,
        "STATIC_PUBLIC_IPV4": ddns_env.get("STATIC_PUBLIC_IPV4", ""),
    })
    network_env["nginx-proxy"]["LETSENCRYPT_EMAIL"] = (
        network_env[public_services[0]]["LETSENCRYPT_EMAIL"]
        if public_services and mode != "local"
        else old_proxy.get("LETSENCRYPT_EMAIL", "")
    )
    return network_env, ddns_env, mode


def setup_firewall(os_info: dict[str, str], mode: str, selected: set[str], lan_cidr: str) -> None:
    distro = os_info.get("ID", "").lower()
    if distro in {"ubuntu", "debian"}:
        if not shutil.which("ufw"):
            print("UFW nie jest zainstalowany; pomijam konfigurację firewalla.")
            return
        privileged(["ufw", "default", "deny", "incoming"])
        privileged(["ufw", "default", "allow", "outgoing"])
        ssh_port = ask("Port SSH do pozostawienia dostępny", "22")
        if not ssh_port.isdigit() or not 1 <= int(ssh_port) <= 65535:
            raise WizardError("Nieprawidłowy port SSH.")
        privileged(["ufw", "allow", f"{ssh_port}/tcp"])
        if lan_cidr:
            privileged(["ufw", "allow", "from", lan_cidr, "to", "any", "port", "9090", "proto", "tcp"])
            if "home-assistant" in selected:
                privileged(["ufw", "allow", "from", lan_cidr, "to", "any", "port", "8123", "proto", "tcp"])
            if "samba" in selected:
                privileged(["ufw", "allow", "from", lan_cidr, "to", "any", "port", "445", "proto", "tcp"])
            if "minecraft" in selected:
                privileged(["ufw", "allow", "from", lan_cidr, "to", "any", "port", "25565", "proto", "tcp"])
        if mode in {"static", "ddns"}:
            privileged(["ufw", "allow", "80/tcp"])
            privileged(["ufw", "allow", "443/tcp"])
        elif "nginx-proxy" in selected and lan_cidr:
            privileged(["ufw", "allow", "from", lan_cidr, "to", "any", "port", "80", "proto", "tcp"])
            privileged(["ufw", "allow", "from", lan_cidr, "to", "any", "port", "443", "proto", "tcp"])
        privileged(["ufw", "--force", "enable"])
        return

    if distro == "fedora" and shutil.which("firewall-cmd"):
        zone = firewalld_zone_for_lan_interface()
        privileged(["firewall-cmd", "--permanent", "--zone", zone, "--add-service=ssh"])
        if lan_cidr:
            for port in ("9090", "8123", "445", "25565"):
                relevant = (
                    port == "9090"
                    or (port == "8123" and "home-assistant" in selected)
                    or (port == "445" and "samba" in selected)
                    or (port == "25565" and "minecraft" in selected)
                )
                if relevant:
                    rule = f'rule family="ipv4" source address="{lan_cidr}" port port="{port}" protocol="tcp" accept'
                    privileged(["firewall-cmd", "--permanent", "--zone", zone, f"--add-rich-rule={rule}"])
        if mode in {"static", "ddns"}:
            privileged(["firewall-cmd", "--permanent", "--zone", zone, "--add-service=http"])
            privileged(["firewall-cmd", "--permanent", "--zone", zone, "--add-service=https"])
        elif "nginx-proxy" in selected and lan_cidr:
            for port in ("80", "443"):
                rule = f'rule family="ipv4" source address="{lan_cidr}" port port="{port}" protocol="tcp" accept'
                privileged(["firewall-cmd", "--permanent", "--zone", zone, f"--add-rich-rule={rule}"])
        privileged(["firewall-cmd", "--reload"])


def firewalld_zone_for_lan_interface() -> str:
    interface = ""
    if shutil.which("ip"):
        route = subprocess.run(
            ["ip", "-o", "-4", "route", "get", "1.1.1.1"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        match = re.search(r"\bdev\s+(\S+)", route.stdout)
        if match:
            interface = match.group(1)

    active = subprocess.run(
        ["firewall-cmd", "--get-active-zones"],
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout
    active_zone = ""
    for line in active.splitlines():
        if line and not line[0].isspace():
            active_zone = line.strip()
        elif interface and line.strip().startswith("interfaces:"):
            interfaces = line.split(":", 1)[1].split()
            if interface in interfaces:
                return active_zone

    default = subprocess.run(
        ["firewall-cmd", "--get-default-zone"],
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout.strip()
    if not default:
        raise WizardError("Nie udało się ustalić domyślnej strefy firewalld.")
    return default


def create_mqtt_password(docker: list[str], service_dir: Path) -> None:
    passwd = service_dir / "config" / "passwd"
    if not passwd.exists():
        print("\nUtwórz użytkownika/hasło MQTT. Hasło wpisujesz bezpośrednio w narzędziu Mosquitto.")
        command = [
            *docker, "run", "--rm", "-it", "-v",
            f"{service_dir / 'config'}:/mosquitto/config",
            "--entrypoint", "mosquitto_passwd", "eclipse-mosquitto:2",
            "-c", "/mosquitto/config/passwd", "mqttuser",
        ]
        subprocess.run(command, check=True)
    for entrypoint, args in (
        ("chown", ["1883:1883", "/mosquitto/config/passwd"]),
        ("chmod", ["640", "/mosquitto/config/passwd"]),
    ):
        run([
            *docker, "run", "--rm", "--user", "0:0", "-v",
            f"{service_dir / 'config'}:/mosquitto/config",
            "--entrypoint", entrypoint, "eclipse-mosquitto:2", *args,
        ])


def configure_minecraft(env: dict[str, str]) -> bool:
    print("Minecraft wymaga świadomej akceptacji EULA: https://www.minecraft.net/en-us/eula")
    if not confirm("Czy akceptujesz Minecraft EULA?", False):
        print("Pominięto Minecraft. Możesz skonfigurować go później.")
        return False
    env["MINECRAFT_EULA"] = "TRUE"
    players = ask("Whitelist (nicki graczy, oddzielone przecinkami)")
    if not players:
        raise WizardError("Whitelist nie może być pusta.")
    env["MINECRAFT_WHITELIST"] = players
    return True


def compose_command(docker: list[str], service_dir: Path, action: str) -> None:
    run([
        *docker, "compose", "--env-file", str(service_dir / ".env"),
        "-f", str(service_dir / "compose.yaml"), action, "-d",
    ])


def load_state() -> set[str]:
    if not STATE_FILE.exists():
        return set()
    try:
        data = json.loads(STATE_FILE.read_text())
        services = data.get("services") if isinstance(data, dict) else None
        if not isinstance(services, list) or not all(isinstance(item, str) for item in services):
            raise WizardError(f"Nieprawidłowy format stanu instalacji: {STATE_FILE}")
        return set(services)
    except (OSError, json.JSONDecodeError):
        raise WizardError(f"Nie można odczytać stanu instalacji: {STATE_FILE}")


def save_state(services: set[str]) -> None:
    existing = load_state()
    existing.update(services)
    temp = STATE_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps({"services": sorted(existing)}, indent=2) + "\n")
    os.chmod(temp, 0o600)
    temp.replace(STATE_FILE)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Konfigurator serwera Homelab")
    parser.add_argument("--version", action="version", version="homelab-wizard 1.0")
    args = parser.parse_args(argv)
    del args
    if not sys.stdin.isatty():
        print("Kreator wymaga terminala interaktywnego.", file=sys.stderr)
        return 2
    try:
        os_info = read_os_release()
        print("Homelab Wizard — konfiguracja systemu i wybranych usług")
        print(f"Wykryty system: {os_info.get('PRETTY_NAME', 'nieznany')}")

        if not shutil.which("docker") or subprocess.run(
            ["docker", "compose", "version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        ).returncode != 0:
            if confirm("Zainstalować Docker Engine, Compose v2 i Cockpit z oficjalnego repozytorium?", True):
                install_packages(os_info)
            else:
                raise WizardError("Docker Engine i Docker Compose v2 są wymagane do wdrażania stosów.")
        elif confirm("Sprawdzić/uzupełnić instalację Cockpit oraz Dockera?", False):
            install_packages(os_info)

        if not shutil.which("docker"):
            raise WizardError("Nie znaleziono polecenia docker po instalacji.")
        docker = docker_prefix()
        configured = load_state()
        selected = select_services(configured)
        if "minecraft" in selected:
            minecraft_env = read_env(CONTAINERS / "minecraft" / ".env")
            if not configure_minecraft(minecraft_env):
                selected.remove("minecraft")
            else:
                write_env(CONTAINERS / "minecraft" / ".env", minecraft_env)
        if not selected:
            print("Nie ma nowych usług do wdrożenia.")
            return 0

        old_values = {name: read_env(CONTAINERS / name / ".env") for name in selected}
        network_env, ddns_env, mode = collect_network(selected, old_values)
        if any(SERVICES.get(name, ("", False, ()))[1] for name in selected):
            selected.add("nginx-proxy")
        ddns_plan = None
        if mode == "ddns":
            public_hosts = sorted({
                values[WEB_ENV[name][1]]
                for name, values in network_env.items()
                if name in WEB_ENV and values.get(WEB_ENV[name][1])
            })
            ddns_plan = ddns_client.collect(public_hosts, ask)

        lan_cidr = ask("Zaufana podsieć LAN dla Cockpit/HA/SMB (CIDR; Enter pomija ograniczone reguły)", "")
        if lan_cidr:
            try:
                network = ipaddress.ip_network(lan_cidr, strict=False)
                if network.version != 4:
                    raise ValueError("Firewall rules in this wizard expect IPv4.")
            except ValueError as exc:
                raise WizardError("Podaj poprawną podsieć LAN IPv4 w zapisie CIDR.") from exc
        if confirm("Zastosować bazowe reguły firewalla systemu?", True):
            setup_firewall(os_info, mode, selected, lan_cidr)
            print("Uwaga: publikowane porty Docker mogą omijać UFW/firewalld. Ogranicz ekspozycję również przez bindowanie i reguły routera/DOCKER-USER.")

        if ddns_plan:
            client, provider, creds = ddns_plan
            path = ddns_client.apply(client, provider, public_hosts, creds, os_info.get("ID", "").lower(), privileged)
            print(f"Klient DDNS {client} zainstalowany; konfiguracja: {path} (chmod 600).")
            print("Uwaga: klient aktualizuje tylko rekord DNS. Router nadal może wymagać przekierowania")
            print("portów 80/443, reguł NAT/firewalla, a przy CGNAT publicznego adresu lub VPN.")
        all_env = {**network_env}
        if "samba" in selected:
            all_env.setdefault("samba", {}).update({
                "SMB_BIND_ADDRESS": network_env.get("nginx-proxy", {}).get("PROXY_BIND_ADDRESS", detect_lan_address()),
                "SAMBA_UID": str(os.getuid()),
            })
        if "jellyfin" in selected:
            default_media = "/mnt/raid/Library" if Path("/mnt/raid/Library").exists() else str(ROOT / "media")
            media = ask(
                "Katalog biblioteki mediów (Jellyfin read-only)",
                old_values.get("jellyfin", {}).get("MEDIA_ROOT", default_media),
            )
            all_env.setdefault("jellyfin", {})["MEDIA_ROOT"] = media
        if "zigbee2mqtt" in selected:
            configured_adapter = old_values.get("zigbee2mqtt", {}).get("ZIGBEE_ADAPTER", "")
            if configured_adapter.startswith("/dev/serial/by-id/replace-with-"):
                configured_adapter = ""
            adapters_dir = Path("/dev/serial/by-id")
            available_adapters = sorted(str(path) for path in adapters_dir.iterdir()) if adapters_dir.is_dir() else []
            default_adapter = configured_adapter or (available_adapters[0] if available_adapters else "")
            adapter = ask("Ścieżka urządzenia Zigbee (np. /dev/serial/by-id/...)", default_adapter)
            if not adapter or not Path(adapter).is_char_device():
                raise WizardError("Podana ścieżka nie wskazuje na istniejące urządzenie znakowe.")
            all_env.setdefault("zigbee2mqtt", {})["ZIGBEE_ADAPTER"] = adapter
        if "minecraft" in selected:
            all_env.setdefault("minecraft", {})["MINECRAFT_BIND_ADDRESS"] = old_values.get(
                "minecraft", {}
            ).get("MINECRAFT_BIND_ADDRESS", detect_lan_address())
        if "home-assistant" in selected:
            all_env.setdefault("home-assistant", {})["TZ"] = ask(
                "Strefa czasowa, np. Europe/Warsaw",
                old_values.get("home-assistant", {}).get("TZ", "Europe/Warsaw"),
            )
        if "nextcloud" in selected and "euro-office" in selected:
            print("Skonfiguruj Euro-Office JWT w aplikacji Nextcloud Office po pierwszym uruchomieniu.")

        for name in selected:
            directory = CONTAINERS / name
            if not (directory / "compose.yaml").is_file():
                raise WizardError(f"Brak compose.yaml dla {name}.")
            updates = all_env.get(name, {})
            write_env(directory / ".env", updates)

        if "mqtt" in selected:
            create_mqtt_password(docker, CONTAINERS / "mqtt")

        print("\nKonfiguracja zapisuje się do lokalnych plików .env (chmod 600).")
        print("Nie publikuj tych plików ani Docker socketu. Zostaną uruchomione wyłącznie wybrane stosy.")
        for name in START_ORDER:
            if name not in selected:
                continue
            service_dir = CONTAINERS / name
            run([
                *docker, "compose", "--env-file", str(service_dir / ".env"),
                "-f", str(service_dir / "compose.yaml"), "config", "--quiet",
            ])
        if not confirm("Uruchomić wybrane stosy teraz?", True):
            save_state(selected)
            print("Konfiguracja gotowa. Uruchom ponownie `bash ./homelab`, aby wdrożyć wybrane usługi.")
            return 0
        for name in START_ORDER:
            if name in selected:
                compose_command(docker, CONTAINERS / name, "up")
        save_state(selected)
        print("\nGotowe. Sprawdź `docker compose ps` w katalogach wybranych usług.")
        print("Dostęp publiczny wymaga poprawnych rekordów DNS, przekierowań portów i sprawdzenia zewnętrznego.")
        return 0
    except (WizardError, ddns_client.DdnsError, subprocess.CalledProcessError, EOFError, KeyboardInterrupt) as exc:
        if isinstance(exc, KeyboardInterrupt):
            print("\nPrzerwano przez użytkownika.", file=sys.stderr)
            return 130
        if isinstance(exc, subprocess.CalledProcessError):
            print(f"Błąd polecenia (kod {exc.returncode}). Popraw przyczynę i uruchom kreator ponownie.", file=sys.stderr)
            return exc.returncode or 1
        print(f"Błąd: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
