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


if __name__ == "__main__":
    unittest.main()
