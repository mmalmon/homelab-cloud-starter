import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wizard"))

import ddns_client
import distro
import updater_setup
import homelab_wizard as wizard


class WizardTests(unittest.TestCase):
    def test_selecting_zigbee2mqtt_includes_mqtt_dependency(self):
        with patch.object(wizard, "ask", return_value="zigbee2mqtt"):
            selected = wizard.select_services(set())
        self.assertEqual(selected, {"zigbee2mqtt", "mqtt"})

    def test_select_services_returns_empty_when_everything_is_configured(self):
        with patch.object(wizard, "ask", return_value=""):
            selected = wizard.select_services(set(wizard.SERVICES))
        self.assertEqual(selected, set())

    def test_django_is_a_web_service_with_proxy_host(self):
        self.assertIn("django", wizard.SERVICES)
        self.assertEqual(wizard.WEB_ENV["django"], ("DJANGO_HOST", "DJANGO_TLS_HOST"))
        self.assertIn("django", wizard.START_ORDER)
        self.assertTrue((wizard.CONTAINERS / "django" / "Dockerfile").exists())

    def test_domain_validation(self):
        self.assertTrue(wizard.validate_domain("media.example.org"))
        self.assertFalse(wizard.validate_domain("media..example.org"))
        self.assertFalse(wizard.validate_domain("-media.example.org"))

    def test_write_env_generates_secret_and_restricts_permissions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / ".env"
            path.with_name(".env.example").write_text(
                "APP_PASSWORD=replace-with-password\nAPP_PORT=8080\n"
            )
            wizard.write_env(path, {})
            values = wizard.read_env(path)

            self.assertRegex(values["APP_PASSWORD"], re.compile(r"^[0-9a-f]{64}$"))
            self.assertEqual(values["APP_PORT"], "8080")
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def test_ddns_and_wud_are_not_wizard_services(self):
        self.assertFalse(any(name.startswith("ddns") or name == "wud" for name in wizard.SERVICES))
        self.assertFalse((wizard.CONTAINERS / "wud").exists())

    def test_public_network_does_not_expose_zigbee_admin_panel(self):
        answers = iter([
            "2",
            "example.org",
            "8.8.8.8",
            "192.168.1.10",
            "cloud.example.org",
            "admin@example.org",
        ])
        with patch.object(wizard, "ask", side_effect=lambda *_args: next(answers)), patch.object(
            wizard, "detect_lan_address", return_value="192.168.1.10"
        ):
            network_env, _, mode = wizard.collect_network(
                {"nextcloud", "zigbee2mqtt"}, {}
            )

        self.assertEqual(mode, "static")
        self.assertEqual(network_env["zigbee2mqtt"]["ZIGBEE2MQTT_HOST"], "")
        self.assertEqual(network_env["zigbee2mqtt"]["ZIGBEE2MQTT_TLS_HOST"], "")
        self.assertEqual(network_env["nextcloud"]["NEXTCLOUD_TLS_HOST"], "cloud.example.org")

    def test_ddns_mode_asks_only_for_hostnames_and_adds_no_service(self):
        answers = iter(["3", "example.org", "192.168.1.10", "cloud.example.org", "admin@example.org"])
        with patch.object(wizard, "ask", side_effect=lambda *_args: next(answers)), patch.object(
            wizard, "detect_lan_address", return_value="192.168.1.10"
        ):
            network_env, ddns_env, mode = wizard.collect_network({"nextcloud"}, {})
        self.assertEqual(mode, "ddns")
        self.assertEqual(ddns_env, {})
        self.assertEqual(network_env["nextcloud"]["NEXTCLOUD_TLS_HOST"], "cloud.example.org")

    def test_fedora_uses_dnf5_repository_syntax(self):
        with patch.object(wizard, "privileged") as privileged:
            wizard.install_packages({"ID": "fedora"})

        calls = [call.args[0] for call in privileged.call_args_list]
        self.assertIn(
            ["dnf", "config-manager", "addrepo", "--from-repofile=https://download.docker.com/linux/fedora/docker-ce.repo"],
            calls,
        )

    def test_firewalld_uses_lan_interface_zone_not_docker_zone(self):
        results = iter([
            SimpleNamespace(stdout="1.1.1.1 dev eno1 src 192.168.1.10\n"),
            SimpleNamespace(stdout="docker\n  interfaces: docker0\npublic\n  interfaces: eno1\n"),
        ])
        with patch.object(wizard.shutil, "which", return_value="/usr/sbin/ip"), patch.object(
            wizard.subprocess, "run", side_effect=lambda *_args, **_kwargs: next(results)
        ):
            zone = wizard.firewalld_zone_for_lan_interface()
        self.assertEqual(zone, "public")

    def test_mqtt_password_file_is_owned_by_container_user(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Path(temp_dir) / "config"
            config.mkdir()
            (config / "passwd").touch()
            with patch.object(wizard, "run") as run:
                wizard.create_mqtt_password(["docker"], Path(temp_dir))

        calls = [call.args[0] for call in run.call_args_list]
        self.assertIn("chown", calls[0])
        self.assertIn("1883:1883", calls[0])
        self.assertIn("chmod", calls[1])
        self.assertIn("640", calls[1])


class DdnsClientTests(unittest.TestCase):
    def test_ddclient_duckdns_uses_labels_without_suffix(self):
        text = ddns_client.render_ddclient(
            "duckdns", ["cloud.duckdns.org", "photos.duckdns.org"], {"password": "token123"}
        )
        self.assertIn("protocol=duckdns\npassword=token123\ncloud,photos\n", text)

    def test_ddclient_cloudflare_uses_zone_and_full_hostnames(self):
        text = ddns_client.render_ddclient(
            "cloudflare", ["cloud.example.org"], {"zone": "example.org", "password": "tok"}
        )
        self.assertIn("zone=example.org", text)
        self.assertTrue(text.endswith("cloud.example.org\n"))

    def test_inadyn_noip_block(self):
        text = ddns_client.render_inadyn(
            "noip", ["a.ddns.net", "b.ddns.net"], {"login": "user", "password": "pw"}
        )
        self.assertIn("provider no-ip.com {", text)
        self.assertIn('hostname = { "a.ddns.net", "b.ddns.net" }', text)

    def test_rejects_unsafe_secret_and_foreign_duckdns_host(self):
        with self.assertRaises(ddns_client.DdnsError):
            ddns_client.render_ddclient("noip", ["a.ddns.net"], {"login": "u", "password": "p w\nx"})
        with self.assertRaises(ddns_client.DdnsError):
            ddns_client.render_inadyn("duckdns", ["cloud.example.org"], {"password": "t"})

    def test_apply_installs_writes_private_config_and_enables_service(self):
        calls = []
        privileged = lambda cmd, **_: calls.append(cmd)
        path = ddns_client.apply(
            "ddclient", "duckdns", ["cloud.duckdns.org"], {"password": "t"}, "fedora", privileged
        )
        self.assertEqual(str(path), "/etc/ddclient/ddclient.conf")
        self.assertIn(["dnf", "install", "-y", "ddclient"], calls)
        self.assertTrue(any(c[:3] == ["install", "-m", "0600"] for c in calls))
        self.assertIn(["systemctl", "enable", "--now", "ddclient"], calls)

    def test_skip_choice_installs_nothing(self):
        self.assertIsNone(ddns_client.collect(["a.example.org"], lambda *_: "3"))


class UpdaterSetupTests(unittest.TestCase):
    def answers(self, values):
        it = iter(values)
        return lambda prompt, default="": next(it) or default

    def test_updater_is_a_web_wizard_service(self):
        self.assertTrue(wizard.SERVICES["updater"][1])
        self.assertEqual(wizard.WEB_ENV["updater"], ("UPDATER_HOST", "UPDATER_TLS_HOST"))
        self.assertIn("updater", wizard.START_ORDER)

    def test_collect_without_smtp_uses_outbox_and_https_base_url(self):
        env = updater_setup.collect({}, "up.example.org", "up.example.org", self.answers([""]))
        self.assertEqual(env["BASE_URL"], "https://up.example.org")
        self.assertEqual(env["SMTP_HOST"], "")
        self.assertEqual(env["SMTP_PASSWORD"], "")

    def test_collect_with_smtp_reads_settings_and_secret_from_getpass(self):
        answers = self.answers(["smtp.example.org", "me@example.org", "", "starttls", "", "me@example.org"])
        with patch("updater_setup.getpass.getpass", return_value="s3cretPass"):
            env = updater_setup.collect({}, "up.example.org", "", answers)
        self.assertEqual(env["BASE_URL"], "http://up.example.org")
        self.assertEqual(env["MAIL_TO"], "me@example.org")
        self.assertEqual(env["SMTP_PORT"], "587")
        self.assertEqual(env["SMTP_PASSWORD"], "s3cretPass")

    def test_collect_rejects_plain_smtp_and_unsafe_password(self):
        with self.assertRaises(updater_setup.UpdaterError):
            updater_setup.collect({}, "h", "h", self.answers(["smtp.x.org", "a@x.org", "", "none"]))
        answers = self.answers(["smtp.x.org", "a@x.org", "", "ssl", "", "login"])
        with patch("updater_setup.getpass.getpass", return_value="bad pass"):
            with self.assertRaises(updater_setup.UpdaterError):
                updater_setup.collect({}, "h", "h", answers)

    def test_timer_units_run_as_user_and_reject_bad_user(self):
        units = updater_setup.render_units(Path("/srv/homelab/containers/updater"), "maciek")
        self.assertIn("User=maciek", units["homelab-updater-apply.service"])
        self.assertIn("updater.py check", units["homelab-updater-check.service"])
        self.assertIn("OnUnitActiveSec=1min", units["homelab-updater-apply.timer"])
        with self.assertRaises(updater_setup.UpdaterError):
            updater_setup.render_units(Path("/srv/x"), "bad user")


class DiscoveryTests(unittest.TestCase):
    def make_service(self, root, name, manifest=None, compose=True):
        directory = Path(root) / name
        directory.mkdir()
        if compose:
            (directory / "compose.yaml").write_text("services: {}\n")
        if manifest is not None:
            (directory / "wizard.json").write_text(manifest)

    def test_every_container_with_compose_has_a_valid_manifest(self):
        for compose in (wizard.CONTAINERS).glob("*/compose.yaml"):
            self.assertTrue(
                compose.parent.name in wizard._DISCOVERED,
                f"{compose.parent.name}: brak lub błędny wizard.json",
            )

    def test_new_container_folder_is_discovered_with_web_and_order(self):
        with tempfile.TemporaryDirectory() as root:
            self.make_service(
                root, "gitea",
                '{"title": "Gitea", "order": 5, "web": {"host_env": "GITEA_HOST", "tls_env": "GITEA_TLS_HOST"}}',
            )
            found = wizard.discover_services(Path(root))
        self.assertEqual(found["gitea"]["web"], ("GITEA_HOST", "GITEA_TLS_HOST"))
        self.assertTrue(found["gitea"]["public"])
        self.assertEqual(found["gitea"]["order"], 5)

    def test_invalid_missing_and_unresolved_manifests_are_skipped(self):
        with tempfile.TemporaryDirectory() as root:
            self.make_service(root, "nomanifest")
            self.make_service(root, "badjson", "{not json")
            self.make_service(root, "badenv", '{"title": "X", "web": {"host_env": "bad-key", "tls_env": "X_TLS"}}')
            self.make_service(root, "orphan", '{"title": "O", "requires": ["missing"]}')
            self.make_service(root, "nocompose", '{"title": "N"}', compose=False)
            self.make_service(root, "ok", '{"title": "OK"}')
            with patch("sys.stderr"):
                found = wizard.discover_services(Path(root))
        self.assertEqual(list(found), ["ok"])

    def test_nginx_proxy_is_hidden_but_started_first(self):
        self.assertNotIn("nginx-proxy", wizard.SERVICES)
        self.assertEqual(wizard.START_ORDER[0], "nginx-proxy")
        self.assertIn("zigbee2mqtt", wizard.NON_PUBLIC)
        self.assertLess(wizard.START_ORDER.index("mqtt"), wizard.START_ORDER.index("zigbee2mqtt"))


class FlowOrderTests(unittest.TestCase):
    def test_network_is_chosen_before_the_service_list(self):
        calls = []

        def select(_configured):
            calls.append("select_services")
            raise wizard.WizardError("stop")

        def choose(_old):
            calls.append("choose_network")
            return "local", "home.arpa", {}

        with patch.object(wizard.sys.stdin, "isatty", return_value=True), patch.object(
            wizard, "read_os_release", return_value={"ID": "ubuntu"}
        ), patch.object(wizard.shutil, "which", return_value="/usr/bin/docker"), patch.object(
            wizard.subprocess, "run", return_value=SimpleNamespace(returncode=0)
        ), patch.object(wizard, "confirm", return_value=False), patch.object(
            wizard, "docker_prefix", return_value=["docker"]
        ), patch.object(wizard, "load_state", return_value=set()), patch.object(
            wizard, "choose_network", side_effect=choose
        ), patch.object(wizard, "select_services", side_effect=select), patch("sys.stderr"):
            self.assertEqual(wizard.main([]), 1)
        self.assertEqual(calls, ["choose_network", "select_services"])


class DistroTests(unittest.TestCase):
    def test_family_detection_uses_id_and_id_like(self):
        cases = {
            ("ubuntu", ""): "debian", ("debian", ""): "debian", ("linuxmint", "ubuntu debian"): "debian",
            ("pop", "ubuntu debian"): "debian", ("raspbian", "debian"): "debian",
            ("fedora", ""): "fedora", ("nobara", "fedora"): "fedora",
            ("rocky", "rhel centos fedora"): "rhel", ("almalinux", "rhel centos fedora"): "rhel",
            ("rhel", "fedora"): "rhel", ("centos", "rhel fedora"): "rhel",
            ("arch", ""): "arch", ("manjaro", "arch"): "arch", ("endeavouros", "arch"): "arch",
            ("opensuse-tumbleweed", "opensuse suse"): "suse", ("sles", "suse"): "suse",
            ("alpine", ""): "", ("gentoo", ""): "",
        }
        for (distro_id, like), expected in cases.items():
            self.assertEqual(distro.family({"ID": distro_id, "ID_LIKE": like}), expected, distro_id)

    def install_calls(self, os_info):
        with patch.object(wizard, "privileged") as privileged, patch.object(
            wizard.subprocess, "check_output", return_value="amd64\n"
        ), patch.object(wizard, "confirm", return_value=True):
            wizard.install_packages(os_info)
        return [call.args[0] for call in privileged.call_args_list]

    def test_arch_uses_pacman_with_docker_compose_and_cockpit(self):
        calls = self.install_calls({"ID": "manjaro", "ID_LIKE": "arch"})
        self.assertTrue(any(c[:2] == ["pacman", "-Syu"] and "docker-compose" in c and "cockpit" in c for c in calls))
        self.assertIn(["systemctl", "enable", "--now", "docker"], calls)

    def test_suse_uses_zypper(self):
        calls = self.install_calls({"ID": "opensuse-leap", "ID_LIKE": "suse opensuse"})
        self.assertTrue(any(c[0] == "zypper" and "docker-compose" in c for c in calls))

    def test_rocky_uses_centos_docker_repo_with_add_repo(self):
        calls = self.install_calls({"ID": "rocky", "ID_LIKE": "rhel centos fedora"})
        self.assertIn(
            ["dnf", "config-manager", "--add-repo", "https://download.docker.com/linux/centos/docker-ce.repo"], calls
        )

    def test_mint_uses_ubuntu_repo_and_ubuntu_codename(self):
        info = {"ID": "linuxmint", "ID_LIKE": "ubuntu debian", "UBUNTU_CODENAME": "noble", "VERSION_CODENAME": "wilma"}
        self.assertEqual(distro.docker_apt_repo(info), ("ubuntu", "noble"))
        calls = self.install_calls(info)
        self.assertTrue(any("docker.asc" in " ".join(c) and "linux/ubuntu/gpg" in " ".join(c) for c in calls))

    def test_unsupported_distribution_gets_clear_error(self):
        with self.assertRaises(wizard.WizardError):
            wizard.install_packages({"ID": "alpine"})

    def test_ddns_client_install_per_family(self):
        calls = []
        privileged = lambda cmd, **_: calls.append(cmd)
        ddns_client.install_client("ddclient", "arch", privileged)
        ddns_client.install_client("ddclient", "suse", privileged)
        ddns_client.install_client("ddclient", "rhel", privileged)
        self.assertIn(["pacman", "-S", "--noconfirm", "--needed", "ddclient"], calls)
        self.assertIn(["zypper", "--non-interactive", "install", "ddclient"], calls)
        self.assertIn(["dnf", "install", "-y", "epel-release"], calls)
        self.assertEqual(str(ddns_client.config_path("ddclient", "rhel")), "/etc/ddclient.conf")
        self.assertEqual(str(ddns_client.config_path("ddclient", "arch")), "/etc/ddclient/ddclient.conf")
        with self.assertRaises(ddns_client.DdnsError):
            ddns_client.install_client("inadyn", "arch", privileged)
        with self.assertRaises(ddns_client.DdnsError):
            ddns_client.collect(["a.example.org"], lambda *_: "2", "arch")


if __name__ == "__main__":
    unittest.main()
