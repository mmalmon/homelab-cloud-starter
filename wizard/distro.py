"""Linux distribution family detection based on /etc/os-release."""
from __future__ import annotations

RHEL_IDS = {"rhel", "centos", "rocky", "almalinux", "ol", "scientific"}
DEBIAN_IDS = {"debian", "ubuntu", "raspbian"}

FAMILIES = ("debian", "fedora", "rhel", "arch", "suse")


def family(os_info: dict[str, str]) -> str:
    """Return debian, fedora, rhel, arch or suse; empty string when unsupported."""
    distro = os_info.get("ID", "").lower()
    tokens = {distro, *os_info.get("ID_LIKE", "").lower().split()}
    if tokens & RHEL_IDS:
        return "rhel"
    if "fedora" in tokens:
        return "fedora"
    if tokens & DEBIAN_IDS:
        return "debian"
    if tokens & {"arch", "archlinux"}:
        return "arch"
    if tokens & {"suse", "opensuse", "sles"}:
        return "suse"
    return ""


def docker_apt_repo(os_info: dict[str, str]) -> tuple[str, str]:
    """Return (docker repo distro, codename) for Debian-family systems."""
    ubuntu_codename = os_info.get("UBUNTU_CODENAME", "")
    if os_info.get("ID", "").lower() == "ubuntu" or ubuntu_codename:
        codename = ubuntu_codename or os_info.get("VERSION_CODENAME", "")
        return "ubuntu", codename
    return "debian", os_info.get("VERSION_CODENAME", "")


def docker_rpm_repo(os_info: dict[str, str]) -> str:
    """Docker publishes RHEL-compatible packages under 'rhel' and 'centos' repos."""
    return "rhel" if os_info.get("ID", "").lower() == "rhel" else "centos"
