import importlib.util
import os
import shutil
import tempfile
import types
import unittest
from unittest.mock import patch


SOURCE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "updater.py"))


class HostUpdaterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        script = os.path.join(self.tmp.name, "updater.py")
        shutil.copyfile(SOURCE, script)
        spec = importlib.util.spec_from_file_location("updater_under_test", script)
        self.updater = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.updater)

    def tearDown(self):
        self.tmp.cleanup()

    def test_private_json_creates_restricted_directory_and_file(self):
        path = os.path.join(self.tmp.name, "state", "pending", "job.json")
        self.updater.write_private_json(path, {"safe": True})
        self.assertEqual(os.stat(os.path.dirname(path)).st_mode & 0o777, 0o700)
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def test_smtp_credentials_require_encryption(self):
        self.updater.ENV = {
            "SMTP_HOST": "smtp.example.test",
            "MAIL_TO": "user@example.test",
            "SMTP_USER": "user",
            "SMTP_PASSWORD": "not-a-real-password",
            "SMTP_SECURITY": "none",
        }
        with patch.object(self.updater.smtplib, "SMTP") as smtp:
            with self.assertRaisesRegex(ValueError, "bez szyfrowania"):
                self.updater.send_mail("test", "message")
        smtp.assert_not_called()

    def test_wait_ok_requires_expected_image(self):
        result = types.SimpleNamespace(
            returncode=0,
            stdout="sha256:old|running|healthy|0",
            stderr="",
        )
        clock = types.SimpleNamespace(value=0)

        def tick():
            clock.value += 0.1
            return clock.value

        clock.time = tick
        clock.sleep = lambda _seconds: None
        with patch.object(self.updater, "run", return_value=result), patch.object(self.updater, "time", clock):
            self.assertFalse(self.updater.wait_ok("example", "sha256:new", timeout=1))


if __name__ == "__main__":
    unittest.main()
