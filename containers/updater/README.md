# Updater — aktualizacje kontenerów z akceptacją e-mail

Wzór działającego Updatera (ten sam kod co w osobnym repozytorium
[homelab-container-updater](https://github.com/mmalmon/homelab-container-updater)).
Najprościej zainstalować go kreatorem (`bash ./homelab`, usługa `updater`):
zapyta o SMTP, ustawi hasło i harmonogram systemd. Skrypt na hoście steruje
Dockerem (uprawnienia równoważne root), więc wybieraj go świadomie. Instalacja
ręczna jest opisana niżej.

## Jak działa

1. `updater.py check` (host) sprawdza, czy uruchomione kontenery Compose mają
   nowszy obraz, i wysyła e-mail z jednorazowym linkiem (ważny 4 godziny).
2. Link tylko wyświetla propozycję; zatwierdzenie wymaga osobnego hasła
   (`updater.py set-password`). Zwykły GET nigdy nie zatwierdza aktualizacji.
3. `updater.py apply` wykonuje zatwierdzone zadania: ograniczona kopia (pliki
   Compose, `.env`, `docker inspect`, zrzuty SQL), aktualizacja usługi, test
   działania i próba cofnięcia obrazu. Aktualizacje pakietów systemu są tylko
   raportowane.

Kontener `updater-web` nie montuje gniazda Docker, działa jako `read_only`
z `cap_drop: ALL`, bez publikowanych portów — jest dostępny tylko przez
`nginx-proxy` (sieć `homelab-proxy`).

## Instalacja

```bash
cd containers/updater
cp .env.example .env && chmod 600 .env
id    # wpisz UID/GID konta uruchamiającego skrypt jako APP_UID/APP_GID
```

W `.env` ustaw `UPDATER_HOST` (hostname w `nginx-proxy`), `BASE_URL`
(publiczny adres HTTPS), `MAIL_TO`, `MAIL_FROM` i dane SMTP
(`SMTP_SECURITY=starttls` lub `ssl`; dane SMTP nie są wysyłane bez
szyfrowania). Bez SMTP wiadomości trafiają do `state/outbox/`. Sieć
`homelab-proxy` powstaje po uruchomieniu `nginx-proxy` przez kreator.

```bash
docker compose config --quiet
docker compose up -d
python3 updater.py set-password
python3 updater.py test-mail
python3 updater.py check --dry-run
```

Harmonogram (cron/systemd timer, to samo konto): `python3 updater.py apply`
co minutę oraz `python3 updater.py check` w rozsądnych odstępach (np. raz
dziennie).

## Ograniczenia i bezpieczeństwo

- Kopia **nie obejmuje** wolumenów ani danych aplikacji (np. plików
  Nextcloud, bibliotek Immich). Miej niezależne, przetestowane kopie;
  cofnięcie obrazu nie cofa migracji bazy.
- Używaj HTTPS; logi reverse proxy mogą zawierać jednorazowy token w URL.
- Nie ufamy nagłówkom przekazywanym przez proxy — limit prób liczony jest po
  adresie TCP (czyli zwykle proxy).
- `.env`, `state/` i `backups/` zawierają sekrety i są ignorowane przez Git.
- Testy: `python3 -m unittest discover -s tests`.

Alternatywa do samego monitoringu wydań: [What's Up Docker](https://github.com/getwud/wud).
