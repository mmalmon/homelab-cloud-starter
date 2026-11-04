import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wizard"))
import homelab_wizard as wizard


class FearCombatTests(unittest.TestCase):
    def test_discovery_has_no_proxy_dependency(self):
        with patch.object(wizard, "ask", return_value="fear-combat"):
            selected = wizard.select_services(set())
        self.assertEqual(selected, {"fear-combat"})
        self.assertNotIn("fear-combat", wizard.WEB_ENV)
        self.assertIn("fear-combat", wizard.START_ORDER)

    def prepare(self, root):
        directory = Path(root) / "fear-combat"
        (directory / "server" / "FEAR").mkdir(parents=True)
        for name in ("fearserver.bin", "libGameServer.so"):
            (directory / "server" / "FEAR" / name).write_bytes(b"fixture")
        (directory / "config").mkdir()
        (directory / "config" / "ServerOptions.example.txt").write_text("LANOnly=1\nPort=27888\n")
        return directory

    def configure(self, root, env, answers):
        with patch.object(wizard, "CONTAINERS", Path(root)), patch.object(
            wizard, "ask", side_effect=answers
        ), patch.object(wizard, "detect_lan_address", return_value="192.168.1.10"), patch.object(
            wizard.os, "getuid", return_value=1000, create=True
        ), patch.object(wizard.os, "getgid", return_value=1000, create=True):
            wizard.configure_fear(env)

    def test_missing_binaries_rejected_before_creating_data(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(wizard.WizardError):
                self.configure(root, {}, [])
            self.assertFalse((Path(root) / "fear-combat" / "server" / "user").exists())

    def test_creates_lan_config_and_preserves_existing_config(self):
        with tempfile.TemporaryDirectory() as root:
            directory = self.prepare(root)
            env = {}
            self.configure(root, env, ["192.168.1.10", "27900"])
            self.assertEqual(env["FEAR_PORT"], "27900")
            self.assertEqual(env["FEAR_UID"], "1000")
            config = directory / "config" / "ServerOptions.txt"
            self.assertIn("LANOnly=1", config.read_text())
            config.write_text("private settings\n")
            self.configure(root, env, ["192.168.1.10", "27900"])
            self.assertEqual(config.read_text(), "private settings\n")

    def test_bad_port_or_wildcard_rejected_without_data_changes(self):
        for answers in (["192.168.1.10", "0"], ["192.168.1.10", "65536"], ["0.0.0.0"]):
            with self.subTest(answers=answers), tempfile.TemporaryDirectory() as root:
                directory = self.prepare(root)
                with self.assertRaises(wizard.WizardError):
                    self.configure(root, {}, answers)
                self.assertFalse((directory / "server" / "user").exists())

    def test_ufw_uses_custom_udp_port_only_for_lan(self):
        with patch.object(wizard.shutil, "which", return_value="/usr/bin/ufw"), patch.object(
            wizard, "ask", return_value="22"
        ), patch.object(wizard, "privileged") as privileged:
            wizard.setup_firewall({"ID": "ubuntu"}, "static", {"fear-combat"}, "192.168.1.0/24", "27900")
        calls = [c.args[0] for c in privileged.call_args_list]
        self.assertIn(["ufw", "allow", "from", "192.168.1.0/24", "to", "any", "port", "27900", "proto", "udp"], calls)
        self.assertNotIn(["ufw", "allow", "27900/udp"], calls)

    def test_firewalld_uses_custom_udp_port_and_no_rule_without_lan(self):
        with patch.object(wizard.shutil, "which", return_value="/usr/bin/firewall-cmd"), patch.object(
            wizard, "firewalld_zone_for_lan_interface", return_value="public"
        ), patch.object(wizard, "privileged") as privileged:
            wizard.setup_firewall({"ID": "fedora"}, "local", {"fear-combat"}, "192.168.1.0/24", "27900")
            udp = [c.args[0] for c in privileged.call_args_list if "protocol=\"udp\"" in " ".join(c.args[0])]
            self.assertEqual(len(udp), 1)
            self.assertIn('port="27900"', udp[0][-1])
            privileged.reset_mock()
            wizard.setup_firewall({"ID": "fedora"}, "static", {"fear-combat"}, "", "27900")
            self.assertFalse(any("udp" in " ".join(c.args[0]) for c in privileged.call_args_list))


if __name__ == "__main__":
    unittest.main()
