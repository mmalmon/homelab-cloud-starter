import base64
import hashlib
import json
import os
import secrets
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "web"))
import web


class ApprovalWebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), web.H)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = "http://127.0.0.1:%d" % cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()
        cls.server.server_close()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        web.STATE = self.tmp.name
        with web.FAILS_LOCK:
            web.FAILS.clear()
        os.makedirs(os.path.join(web.STATE, "pending"))
        os.makedirs(os.path.join(web.STATE, "approved"))
        self.token = secrets.token_urlsafe(32)
        self.pending_path = os.path.join(
            web.STATE,
            "pending",
            hashlib.sha256(self.token.encode()).hexdigest() + ".json",
        )
        with open(self.pending_path, "w") as f:
            json.dump({
                "expires_at": 4_000_000_000,
                "items": [{"container": "demo", "image": "example/demo:1"}],
            }, f)
        password = "a-secure-test-password"
        salt = os.urandom(16)
        digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
        with open(os.path.join(web.STATE, "password.json"), "w") as f:
            json.dump({
                "salt": base64.b64encode(salt).decode(),
                "hash": base64.b64encode(digest).decode(),
            }, f)
        self.password = password

    def tearDown(self):
        self.tmp.cleanup()

    def request(self, method="GET", body=None, headers=None):
        url = self.base_url + "/updates/approve?t=" + self.token
        return urlopen(Request(url, data=body, headers=headers or {}, method=method))

    def test_get_displays_update_without_approving(self):
        response = self.request()
        self.assertEqual(response.status, 200)
        self.assertIn(b"demo", response.read())
        self.assertTrue(os.path.exists(self.pending_path))
        self.assertEqual(os.listdir(os.path.join(web.STATE, "approved")), [])

    def test_password_approval_moves_job_once(self):
        form = urlencode({"t": self.token, "p": self.password}).encode()
        response = self.request("POST", form, {"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(response.status, 200)
        self.assertFalse(os.path.exists(self.pending_path))
        approved = os.listdir(os.path.join(web.STATE, "approved"))
        self.assertEqual(len(approved), 1)
        with open(os.path.join(web.STATE, "approved", approved[0])) as f:
            self.assertIn("approved_at", json.load(f))

    def test_forwarded_ip_header_is_not_trusted(self):
        request = Request(
            self.base_url + "/updates/approve?t=invalid",
            headers={"X-Real-IP": "203.0.113.99"},
        )
        with self.assertRaises(HTTPError) as error:
            urlopen(request)
        error.exception.close()
        self.assertIn("127.0.0.1", web.FAILS)
        self.assertNotIn("203.0.113.99", web.FAILS)

    def test_oversized_post_is_rejected(self):
        form = b"x" * 1025
        with self.assertRaises(HTTPError) as error:
            self.request("POST", form, {"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(error.exception.code, 413)
        error.exception.close()


if __name__ == "__main__":
    unittest.main()
