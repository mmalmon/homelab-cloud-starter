"""Minimalny serwer zatwierdzania aktualizacji bez dostepu do Dockera."""
import base64, hashlib, hmac, html, json, os, re, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

STATE = os.environ.get("STATE_DIR", "/state")
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")
FAILS = {}
FAILS_LOCK = threading.Lock()


def find_job(token):
    if not TOKEN_RE.match(token or ""):
        return None, None
    h = hashlib.sha256(token.encode()).hexdigest()
    path = os.path.join(STATE, "pending", h + ".json")
    if not os.path.isfile(path):
        return None, None
    with open(path) as f:
        return path, json.load(f)


def pw_ok(pw):
    try:
        encoded = (pw or "").encode()
        if len(encoded) > 200:
            return False
        with open(os.path.join(STATE, "password.json")) as f:
            d = json.load(f)
        salt = base64.b64decode(d["salt"])
        h = hashlib.scrypt(encoded, salt=salt, n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(h, base64.b64decode(d["hash"]))
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False


def page(title, body, code=200):
    doc = ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
           "<meta name=robots content=noindex><title>%s</title>"
           "<body style='font-family:sans-serif;max-width:560px;margin:3em auto;padding:0 1em'>"
           "<h2>%s</h2>%s</body>" % (html.escape(title), html.escape(title), body))
    return code, doc.encode()


class H(BaseHTTPRequestHandler):
    server_version = "updater"
    sys_version = ""

    def log_message(self, fmt, *a):
        pass

    def ip(self):
        return self.client_address[0]

    def limited(self):
        now = time.time()
        with FAILS_LOCK:
            FAILS[self.ip()] = [t for t in FAILS.get(self.ip(), []) if now - t < 600]
            return len(FAILS[self.ip()]) >= 10

    def failed(self):
        with FAILS_LOCK:
            FAILS.setdefault(self.ip(), []).append(time.time())

    def send(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def check(self, token):
        if self.limited():
            return None, None, page("Zbyt wiele prob", "<p>Sprobuj pozniej.</p>", 429)
        path, job = find_job(token)
        if not job:
            self.failed()
            return None, None, page("Link nieprawidlowy", "<p>Link jest nieprawidlowy lub zostal juz uzyty.</p>", 404)
        if time.time() > job["expires_at"]:
            return None, None, page("Link wygasl", "<p>Link byl wazny 4 godziny i wygasl. Poczekaj na kolejne powiadomienie.</p>", 410)
        return path, job, None

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/updates/health":
            return self.send(200, b"ok")
        if u.path != "/updates/approve":
            return self.send(*page("Nie znaleziono", "", 404))
        token = parse_qs(u.query).get("t", [""])[0]
        path, job, err = self.check(token)
        if err:
            return self.send(*err)
        rows = "".join("<li><b>%s</b> (%s)</li>" % (html.escape(i["container"]), html.escape(i["image"]))
                       for i in job["items"])
        exp = time.strftime("%Y-%m-%d %H:%M", time.localtime(job["expires_at"]))
        body = ("<p>Dostepne aktualizacje:</p><ul>%s</ul>"
                "<p>Przed aktualizacja zostanie wykonany backup, a w razie bledu - automatyczny rollback.</p>"
                "<p>Link wazny do %s.</p>"
                "<form method=post action=/updates/approve><input type=hidden name=t value='%s'>"
                "<p><input type=password name=p placeholder='Haslo' required autocomplete=current-password "
                "style='padding:.6em;font-size:1em'></p>"
                "<button style='padding:.7em 1.5em;font-size:1.1em'>Zaktualizuj teraz</button></form>"
                % (rows, exp, html.escape(token)))
        self.send(*page("Zatwierdzenie aktualizacji", body))

    def do_POST(self):
        if urlparse(self.path).path != "/updates/approve":
            return self.send(*page("Nie znaleziono", "", 404))
        try:
            n = int(self.headers.get("Content-Length") or "")
        except ValueError:
            return self.send(*page("Nieprawidlowe zadanie", "<p>Brak prawidlowej dlugosci formularza.</p>", 400))
        if n < 0:
            return self.send(*page("Nieprawidlowe zadanie", "<p>Nieprawidlowy formularz.</p>", 400))
        if n > 1024:
            return self.send(*page("Formularz za duzy", "<p>Sprobuj ponownie.</p>", 413))
        if self.headers.get_content_type() != "application/x-www-form-urlencoded":
            return self.send(*page("Nieprawidlowe zadanie", "<p>Nieobslugiwany typ formularza.</p>", 415))
        form = parse_qs(self.rfile.read(n).decode("utf-8", "ignore"))
        token = form.get("t", [""])[0]
        path, job, err = self.check(token)
        if err:
            return self.send(*err)
        if not pw_ok(form.get("p", [""])[0]):
            self.failed()
            return self.send(*page("Bledne haslo", "<p>Haslo nieprawidlowe. Wroc i sprobuj ponownie (link nadal wazny).</p>", 403))
        job["approved_at"] = time.time()
        job["approved_ip"] = self.ip()
        approved = os.path.join(STATE, "approved")
        os.makedirs(approved, mode=0o700, exist_ok=True)
        os.chmod(approved, 0o700)
        dst = os.path.join(approved, os.path.basename(path))
        try:
            fd = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return self.send(*page("Link juz wykorzystany", "<p>To zadanie zostalo juz zatwierdzone.</p>", 409))
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(job, f)
                f.flush()
                os.fsync(f.fileno())
            os.remove(path)
        except Exception:
            try:
                os.remove(dst)
            except FileNotFoundError:
                pass
            raise
        self.send(*page("Zatwierdzono", "<p>Aktualizacja zostanie uruchomiona w ciagu minuty. "
                        "Wynik dostaniesz e-mailem.</p>"))


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), H).serve_forever()
