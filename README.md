# Homelab Cloud Starter

Przykładowy homelab na Docker Compose z kreatorem, który startuje od czystego
Linuksa: instaluje Docker, Cockpit i firewall, pyta o usługi i domeny, zapisuje
konfigurację `.env` oraz uruchamia wybrane kontenery za `nginx-proxy`.

Konfiguracja jest szablonem: nie zawiera ustawień konkretnego serwera,
prywatnych domen, adresów IP ani danych dostępowych. **Przed wystawieniem do
Internetu zapoznaj się z [ograniczeniami kreatora](docs/homelab-wizard.md)
i [zasadami bezpieczeństwa](docs/security.md).**

## Szybki start

Na nowym hoście z Ubuntu/Debianem, Fedorą, RHEL (Rocky, Alma), Archem lub openSUSE (przygotowanie serwera opisuje
[poradnik Ubuntu Server + Docker + Cockpit + firewall](docs/ubuntu-docker-cockpit.md)):

```bash
git clone https://github.com/mmalmon/homelab-cloud-starter.git
cd homelab-cloud-starter
bash ./homelab
```

Kreator może zainstalować Docker Engine, Compose v2, Cockpit i skonfigurować
podstawowy firewall. Pyta o wybrane usługi, domeny oraz stały publiczny adres
IP albo DDNS (z opcjonalnym klientem na hoście), tworzy lokalne pliki `.env` z uprawnieniami
`600` i uruchamia tylko wybrane stosy. Późniejsze uruchomienie `bash ./homelab`
pozwala dodać kolejne usługi bez nadpisywania istniejących sekretów — z
właściwą konfiguracją `nginx-proxy`. Kolejność: Docker i Cockpit, tryb sieci
(IP/DDNS), lista usług. Usługi wykrywane są z `containers/*/wizard.json`, więc
własny kontener dodasz bez zmian w kodzie ([jak](containers/README.md)).

## Struktura repozytorium

```text
homelab               # skrypt uruchamiający kreator
wizard/               # kod kreatora
containers/<usługa>/  # compose.yaml, .env.example (+ Dockerfile, gdy potrzebny)
docs/                 # dokumentacja
tests/                # testy kreatora
```

Każda aplikacja ma osobny katalog w [`containers/`](containers/). Dockerfile
jest dodawany tylko, gdy serwis wymaga własnego obrazu (np. Django). Dane
trwałe są w podkatalogu `data/` każdej usługi i nie trafiają do Git.

## Usługi dostępne w kreatorze

- **Nextcloud** — pliki, kalendarz i współpraca; z PostgreSQL i Redis.
- **Immich** — zdjęcia i wideo, odpowiednik Zdjęć Google. Aplikacja mobilna na
  Androida i iOS automatycznie synchronizuje zdjęcia z telefonów
  ([szczegóły](containers/immich/README.md)).
- **nginx-proxy** — routing domen/subdomen do usług HTTP; dla publicznego
  HTTPS używa companion ACME. Działa ze stałym IP lub z [DDNS](docs/ddns.md);
  kreator może zainstalować klienta DDNS na hoście (`ddclient`/`inadyn`) —
  nadal może być potrzebna konfiguracja routera, NAT i firewalla.
- **Home Assistant, Mosquitto MQTT i Zigbee2MQTT** — automatyka domowa;
  Zigbee2MQTT wymaga koordynatora.
- **Jellyfin** — odtwarzanie własnych multimediów.
- **WordPress** — strona lub blog z osobną bazą.
- **Django** — zamiennik WordPressa, gdy zamiast gotowego CMS wolisz własną
  stronę lub aplikację WWW. [Szablon](containers/django/) buduje własny obraz
  (Dockerfile) z PostgreSQL i Gunicornem; podmień kod w `containers/django/app/`.
- **Euro-Office** — edycja dokumentów z Nextcloud.
- **Samba** — udziały plików w zaufanej sieci lokalnej.
- **Minecraft** — serwer gry; uruchomienie wymaga zaakceptowania EULA.

Nie wszystkie usługi powinny być kierowane przez reverse proxy: Samba, MQTT
i Minecraft używają innych protokołów, a Home Assistant działa w trybie host.

**Updater** (aktualizacje kontenerów z akceptacją przez e-mail: jednorazowy
link i hasło) ma pełny wzór w [containers/updater](containers/updater/README.md)
— ten sam kod co w osobnym repozytorium
[Homelab Container Updater](https://github.com/mmalmon/homelab-container-updater).
Kreator instaluje go na życzenie (usługa `updater`): pyta o hostname, SMTP
(serwer, nadawca, odbiorca, login, hasło wpisywane bez echa) i hasło
zatwierdzania, a potem ustawia harmonogram systemd. Updater ma dostęp hosta
do Docker API, więc wymaga niezależnych kopii zapasowych.

## Dokumentacja i źródła

- [Pełna mapa homelaba i linki do oficjalnych źródeł](docs/homelab-map.md)
- [Kreator: instalacja hosta, DDNS, ograniczenia](docs/homelab-wizard.md)
- [nginx-proxy](docs/nginx-proxy.md)
- [DDNS i dostęp przy zmiennym IP](docs/ddns.md)
- [Ubuntu Server, Docker i Cockpit](docs/ubuntu-docker-cockpit.md)
- [Dyski RAID i kopie zapasowe](docs/storage-and-raid.md)
- [Kopia zapasowa i odtwarzanie](docs/backup-and-restore.md)
- [Bezpieczeństwo](docs/security.md)

Przed instalacją sprawdź źródła producentów: [Nextcloud](https://nextcloud.com/)
([dokumentacja](https://docs.nextcloud.com/server/latest/admin_manual/)),
[Immich](https://immich.app/) ([dokumentacja](https://docs.immich.app/))
oraz dokumentację każdego wdrażanego programu. Własne aplikacje, w tym oparte
o Django, pozostają odrębnymi projektami — repozytorium nie kopiuje ani nie
publikuje ich kodu.

## Wsparcie

To edukacyjny przykład, nie dystrybucja gotowego serwera. Przed użyciem
produkcyjnym dostosuj wersje obrazów, HTTPS, domeny, zaporę, politykę kopii
zapasowych i odzyskiwanie danych do swojego środowiska.
