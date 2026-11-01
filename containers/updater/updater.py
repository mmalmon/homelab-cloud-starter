#!/usr/bin/env python3
"""Powiadomienia o aktualizacjach obrazow + aktualizacja po zatwierdzeniu linkiem.

  updater.py check [--dry-run]   - pobiera obrazy, wysyla mail z linkiem (wazny 4h)
  updater.py apply               - wykonuje zatwierdzone zadania (backup -> update -> rollback)
  updater.py set-password        - ustawia haslo wymagane na stronie zatwierdzania
  updater.py test-mail           - wysyla probnego maila
"""
import base64, fcntl, getpass, gzip, hashlib, html as html_lib, json, os, secrets, shutil, smtplib, subprocess, sys, tempfile, time
from email.message import EmailMessage

ROOT = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(ROOT, "state")
BACKUPS = os.path.join(ROOT, "backups")
TTL = 4 * 3600
SKIP_CONTAINERS = {"updater-web"}


def load_env():
    env = {}
    p = os.path.join(ROOT, ".env")
    if os.path.isfile(p):
        for line in open(p):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


ENV = load_env()


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def log(msg):
    print("%s %s" % (time.strftime("%F %T"), msg), flush=True)


def private_dir(path):
    os.makedirs(path, mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)


def write_private_json(path, data):
    private_dir(os.path.dirname(path))
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except FileNotFoundError:
            pass
        raise


def send_mail(subject, text, html=None):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = ENV.get("MAIL_FROM") or ENV.get("SMTP_USER") or "updater@localhost"
    msg["To"] = ENV.get("MAIL_TO", "root@localhost")
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    if not ENV.get("SMTP_HOST") or not ENV.get("MAIL_TO"):
        private_dir(os.path.join(STATE, "outbox"))
        p = os.path.join(STATE, "outbox", "%d.eml" % time.time())
        with open(p, "wb") as f:
            f.write(bytes(msg))
        os.chmod(p, 0o600)
        log("SMTP nieskonfigurowany - mail zapisany: %s" % p)
        return False
    port = int(ENV.get("SMTP_PORT", "587"))
    security = ENV.get("SMTP_SECURITY", "starttls")
    if security not in ("starttls", "ssl", "none"):
        raise ValueError("SMTP_SECURITY musi miec wartosc starttls, ssl albo none")
    if security == "none" and (ENV.get("SMTP_USER") or ENV.get("SMTP_PASSWORD")):
        raise ValueError("Nie wysylaj danych SMTP bez szyfrowania; ustaw starttls albo ssl")
    if security == "ssl":
        with smtplib.SMTP_SSL(ENV["SMTP_HOST"], port, timeout=30) as s:
            if ENV.get("SMTP_USER"):
                s.login(ENV["SMTP_USER"], ENV.get("SMTP_PASSWORD", ""))
            s.send_message(msg)
    else:
        with smtplib.SMTP(ENV["SMTP_HOST"], port, timeout=30) as s:
            if security == "starttls":
                s.starttls()
            if ENV.get("SMTP_USER"):
                s.login(ENV["SMTP_USER"], ENV.get("SMTP_PASSWORD", ""))
            s.send_message(msg)
    return True


def running_services():
    result = run(["docker", "ps", "-q"])
    if result.returncode != 0:
        raise RuntimeError("docker ps nie powiodlo sie: %s" % result.stderr.strip())
    ids = result.stdout.split()
    if not ids:
        return {}
    result = run(["docker", "inspect"] + ids)
    if result.returncode != 0:
        raise RuntimeError("docker inspect nie powiodlo sie: %s" % result.stderr.strip())
    data = json.loads(result.stdout)
    out = {}
    for c in data:
        lb = c["Config"]["Labels"] or {}
        name = c["Name"].lstrip("/")
        if "com.docker.compose.project.working_dir" not in lb or name in SKIP_CONTAINERS:
            continue
        key = (lb["com.docker.compose.project.working_dir"], lb["com.docker.compose.service"])
        out[key] = {
            "container": name, "image": c["Config"]["Image"], "old_id": c["Image"],
            "project_dir": key[0], "service": key[1],
            "config_files": lb.get("com.docker.compose.project.config_files", "").split(","),
        }
    return out


def image_id(ref):
    r = run(["docker", "image", "inspect", ref, "--format", "{{.Id}}"])
    return r.stdout.strip() if r.returncode == 0 else None


def cmd_check(dry):
    for sub in ("pending", "approved", "done", "outbox"):
        private_dir(os.path.join(STATE, sub))
    now = time.time()
    for f in os.listdir(os.path.join(STATE, "pending")):
        p = os.path.join(STATE, "pending", f)
        if json.load(open(p))["expires_at"] < now:
            os.remove(p)
    items = []
    for key, s in sorted(running_services().items()):
        r = run(["docker", "pull", "-q", s["image"]])
        if r.returncode != 0:
            log("pomijam %s (%s): pull nieudany/obraz lokalny" % (s["container"], s["image"]))
            continue
        new_id = image_id(s["image"])
        if new_id and new_id != s["old_id"]:
            s["new_id"] = new_id
            items.append(s)
            log("dostepna aktualizacja: %s (%s)" % (s["container"], s["image"]))
    if not items:
        log("brak aktualizacji")
        return
    sig = hashlib.sha256(json.dumps(sorted((i["container"], i["new_id"]) for i in items)).encode()).hexdigest()
    np = os.path.join(STATE, "notified.json")
    notified = json.load(open(np)) if os.path.isfile(np) else {}
    if notified.get("sig") == sig and now - notified.get("ts", 0) < 3 * 86400:
        log("to samo powiadomienie juz wyslane")
        return
    if dry:
        log("dry-run: wyslalbym mail dla %d kontenerow" % len(items))
        return
    base_url = ENV.get("BASE_URL", "").rstrip("/")
    if not base_url.startswith("https://"):
        raise ValueError("Ustaw BASE_URL z adresem HTTPS przed wysylaniem linkow")
    token = secrets.token_urlsafe(32)
    job = {"created_at": now, "expires_at": now + TTL, "items": items}
    p = os.path.join(STATE, "pending", hashlib.sha256(token.encode()).hexdigest() + ".json")
    write_private_json(p, job)
    link = "%s/updates/approve?t=%s" % (base_url, token)
    exp = time.strftime("%F %H:%M", time.localtime(job["expires_at"]))
    lines = "\n".join("  - %s (%s)" % (i["container"], i["image"]) for i in items)
    text = ("Dostepne aktualizacje obrazow:\n%s\n\nZatwierdz (link wazny do %s, jednorazowy):\n%s\n\n"
            "Przed aktualizacja: backup. W razie bledu: automatyczny rollback." % (lines, exp, link))
    li = "".join("<li><b>%s</b> <small>(%s)</small></li>" %
                 (html_lib.escape(i["container"]), html_lib.escape(i["image"])) for i in items)
    safe_link = html_lib.escape(link, quote=True)
    html = ("<p>Dostepne aktualizacje obrazow:</p><ul>%s</ul>"
            "<p><a href='%s' style='background:#2563eb;color:#fff;padding:12px 22px;border-radius:6px;"
            "text-decoration:none;font-weight:bold'>Przejdz do zatwierdzenia</a></p>"
            "<p>Link jest jednorazowy i wazny do %s (4 godziny). Przed aktualizacja zostanie wykonany backup, "
            "a w razie bledu - automatyczny rollback.</p>" % (li, safe_link, exp))
    delivered = send_mail("[Container updater] Dostepne aktualizacje (%d)" % len(items), text, html)
    write_private_json(np, {"sig": sig, "ts": now})
    log("%s dla %d kontenerow" % ("wyslano powiadomienie" if delivered else "zapisano powiadomienie w outbox", len(items)))


def cmd_set_password():
    pw = getpass.getpass("Nowe haslo zatwierdzania (min 12 znakow): ")
    if len(pw) < 12 or len(pw.encode()) > 200 or pw != getpass.getpass("Powtorz: "):
        sys.exit("Haslo za krotkie lub rozne")
    salt = os.urandom(16)
    h = hashlib.scrypt(pw.encode()[:200], salt=salt, n=2**14, r=8, p=1, dklen=32)
    p = os.path.join(STATE, "password.json")
    write_private_json(p, {"salt": base64.b64encode(salt).decode(), "hash": base64.b64encode(h).decode()})
    print("Haslo zapisane")


def check_system(dry):
    r = run(["apt-get", "-s", "dist-upgrade"])
    if r.returncode != 0:
        raise RuntimeError("apt-get -s dist-upgrade nie powiodlo sie: %s" % r.stderr.strip())
    pk = [l.split()[1] for l in r.stdout.splitlines() if l.startswith("Inst ")]
    sec = [l for l in r.stdout.splitlines() if l.startswith("Inst ") and "-security" in l]
    reboot = os.path.exists("/var/run/reboot-required")
    if not pk and not reboot:
        log("system aktualny")
        return
    sig = hashlib.sha256((",".join(sorted(pk)) + str(reboot)).encode()).hexdigest()
    np = os.path.join(STATE, "notified-system.json")
    n = json.load(open(np)) if os.path.isfile(np) else {}
    if n.get("sig") == sig and time.time() - n.get("ts", 0) < 7 * 86400:
        return
    log("system: %d pakietow (%d security), reboot=%s" % (len(pk), len(sec), reboot))
    if dry:
        return
    text = ("Dostepne aktualizacje systemu (apt): %d pakietow, w tym %d bezpieczenstwa.\n%s\n"
            "Wymagany restart: %s\n\nAktualizacje systemowe NIE sa uruchamiane automatycznie. "
            "Wykonaj recznie przez SSH:\n  sudo apt update && sudo apt upgrade%s\n\n"
            "Pakiety: %s" % (len(pk), len(sec), "", "TAK" if reboot else "nie",
                             "\n  sudo reboot" if reboot else "", ", ".join(pk[:40])))
    send_mail("[Container updater] Aktualizacje systemu do wykonania (%d)" % len(pk), text)
    write_private_json(np, {"sig": sig, "ts": time.time()})


def compose(item, *args):
    cmd = ["docker", "compose", "--project-directory", item["project_dir"]]
    for f in item["config_files"]:
        cmd += ["-f", f]
    return run(cmd + list(args), cwd=item["project_dir"])


def wait_ok(name, expected_image_id=None, timeout=180):
    end = time.time() + timeout
    stable = 0
    while time.time() < end:
        r = run(["docker", "inspect", name, "--format",
                 "{{.Image}}|{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}|{{.RestartCount}}"])
        if r.returncode != 0:
            return False
        image, st, health, restarts = (r.stdout.strip().split("|") + ["", "", ""])[:4]
        if st == "exited" or st == "dead" or int(restarts or 0) > 0:
            return False
        if health == "healthy" or (health == "" and st == "running"):
            stable += 1
            if stable >= (1 if health else 6):
                if expected_image_id is None or image == expected_image_id:
                    return True
                stable = 0
        else:
            stable = 0
        if health == "unhealthy":
            return False
        time.sleep(5)
    return False


def backup_item(item, ts):
    d = os.path.join(BACKUPS, ts, item["container"])
    private_dir(BACKUPS)
    private_dir(os.path.join(BACKUPS, ts))
    private_dir(d)
    for f in item["config_files"] + [os.path.join(item["project_dir"], ".env")]:
        if os.path.isfile(f):
            target = os.path.join(d, os.path.basename(f))
            shutil.copyfile(f, target)
            os.chmod(target, 0o600)
    with open(os.path.join(d, "inspect.json"), "w") as f:
        f.write(run(["docker", "inspect", item["container"]]).stdout)
    os.chmod(os.path.join(d, "inspect.json"), 0o600)
    img = item["image"].split("/")[-1].split(":")[0]
    dump = None
    if img in ("mariadb", "mysql"):
        dump = "mariadb-dump -uroot -p\"${MARIADB_ROOT_PASSWORD:-$MYSQL_ROOT_PASSWORD}\" --all-databases --single-transaction --routines --events"
    elif img in ("postgres", "pgvector"):
        dump = "pg_dumpall -U \"$POSTGRES_USER\""
    if dump:
        out = os.path.join(d, "dump.sql.gz")
        with tempfile.TemporaryFile() as err, gzip.open(out, "wb") as target:
            proc = subprocess.Popen(
                ["docker", "exec", item["container"], "sh", "-c", dump],
                stdout=subprocess.PIPE,
                stderr=err,
            )
            shutil.copyfileobj(proc.stdout, target)
            proc.stdout.close()
            status = proc.wait()
            err.seek(0, os.SEEK_END)
            err.seek(max(0, err.tell() - 200))
            detail = err.read().decode("utf-8", "replace")
        os.chmod(out, 0o600)
        if status != 0 or os.path.getsize(out) == 0:
            os.remove(out)
            raise RuntimeError("backup bazy nieudany: %s" % detail)
    return d


def update_item(item, ts):
    name, ref = item["container"], item["image"]
    r = run(["docker", "pull", "-q", ref])
    new_id = image_id(ref)
    if r.returncode != 0 or not new_id:
        return "pominiety (pull nieudany)"
    cur = run(["docker", "inspect", name, "--format", "{{.Image}}"])
    if cur.returncode != 0:
        return "POMINIETY - nie mozna odczytac biezacego obrazu"
    cur = cur.stdout.strip()
    if cur == new_id:
        return "juz aktualny"
    old_id = cur
    try:
        bdir = backup_item(item, ts)
    except Exception as e:
        return "POMINIETY - %s" % e
    rb = "updater-rollback/%s:%s" % (name.lower().replace("_", "-"), ts)
    tagged = run(["docker", "tag", old_id, rb])
    if tagged.returncode != 0:
        return "POMINIETY - nie udalo sie zachowac poprzedniego obrazu"
    deployed = compose(item, "up", "-d", "--no-deps", item["service"])
    if deployed.returncode == 0 and wait_ok(name, expected_image_id=new_id):
        for line in run(["docker", "images", "--format", "{{.Repository}}:{{.Tag}}",
                         "updater-rollback/" + name.lower().replace("_", "-")]).stdout.split():
            if line != rb:
                run(["docker", "rmi", line])
        return "OK (backup: %s)" % bdir
    log("%s: aktualizacja nieudana - rollback" % name)
    restored_tag = run(["docker", "tag", old_id, ref])
    rollback = compose(item, "up", "-d", "--no-deps", "--force-recreate", item["service"]) \
        if restored_tag.returncode == 0 else None
    ok = rollback is not None and rollback.returncode == 0 and wait_ok(name, expected_image_id=old_id)
    return "BLAD -> ROLLBACK %s (backup: %s)" % ("udany" if ok else "NIEUDANY - wymagana interwencja", bdir)


def cmd_apply():
    ap = os.path.join(STATE, "approved")
    if not os.path.isdir(ap) or not [f for f in os.listdir(ap) if f.endswith(".json")]:
        return
    private_dir(os.path.join(STATE, "done"))
    lock = open(os.path.join(STATE, "apply.lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return
    for f in sorted(os.listdir(ap)):
        if not f.endswith(".json"):
            continue
        p = os.path.join(ap, f)
        job = json.load(open(p))
        dest = os.path.join(STATE, "done", f)
        if job["approved_at"] > job["expires_at"]:
            os.replace(p, dest)
            log("zadanie %s po terminie - odrzucone" % f[:8])
            continue
        ts = time.strftime("%Y%m%d-%H%M%S")
        results = []
        for item in sorted(job["items"], key=lambda i: 0 if i["image"].split("/")[-1].split(":")[0] in
                           ("mariadb", "mysql", "postgres", "pgvector", "redis") else 1):
            try:
                res = update_item(item, ts)
            except Exception as e:
                res = "WYJATEK: %s" % e
            log("%s: %s" % (item["container"], res))
            results.append("%s: %s" % (item["container"], res))
        job["results"] = results
        job["finished_at"] = time.time()
        write_private_json(dest, job)
        os.remove(p)
        bad = any(("BLAD" in r or "WYJATEK" in r or "POMINIETY" in r) for r in results)
        send_mail("[Container updater] Aktualizacja kontenerow: %s" % ("PROBLEMY" if bad else "zakonczona"),
                  "Wyniki:\n" + "\n".join(results))
        run(["docker", "image", "prune", "-f"])
    cutoff = time.time() - 30 * 86400
    if os.path.isdir(BACKUPS):
        for d in os.listdir(BACKUPS):
            if os.path.getmtime(os.path.join(BACKUPS, d)) < cutoff:
                shutil.rmtree(os.path.join(BACKUPS, d), ignore_errors=True)


if __name__ == "__main__":
    a = sys.argv[1:] or ["help"]
    if a[0] == "check":
        try:
            cmd_check("--dry-run" in a)
        finally:
            check_system("--dry-run" in a)
    elif a[0] == "set-password":
        cmd_set_password()
    elif a[0] == "apply":
        cmd_apply()
    elif a[0] == "test-mail":
        print(send_mail("[Container updater] Test powiadomien", "Test wysylki z updater.py"))
    else:
        print(__doc__)
