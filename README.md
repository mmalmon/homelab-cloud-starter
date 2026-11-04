# Homelab Cloud Starter

Przykładowy homelab na Docker Compose z kreatorem, który startuje od czystego
Linuksa: instaluje Docker, Cockpit i firewall, pyta o usługi i domeny, zapisuje
konfigurację `.env` oraz uruchamia wybrane kontenery za `nginx-proxy`.

Konfiguracja jest szablonem: nie zawiera ustawień konkretnego serwera,
prywatnych domen, adresów IP ani danych dostępowych. **Przed wystawieniem do
Internetu zapoznaj się z [ograniczeniami kreatora](docs/homelab-wizard.md)
i [zasadami bezpieczeństwa](docs/security.md).**

## Zacznij tutaj

Jeśli dopiero poznajesz homelab, przeczytaj [artykuł z pierwszym ćwiczeniem Nginx](https://master-homelab.pl/homelab/domowy-homelab-z-dockerem-i-kontenerami-jak-dziala-moj-serwer/).
Starter jest edukacyjnym szablonem inspirowanym moim serwerem. Nie odtwarza go
jeden do jednego: artykuł opisuje m.in. Portainer oraz Nginx z Certbotem,
a kreator instaluje Cockpit do administracji hostem oraz nginx-proxy
z acme-companion do obsługi domen i publicznych certyfikatów HTTPS.
Portainer zarządza kontenerami; Cockpit przede wszystkim samym systemem.

Proponowana kolejność nauki:

1. Wykonaj lokalne ćwiczenie Nginx z artykułu i usuń je po zakończeniu.
2. Na osobnym hoście testowym wybierz w kreatorze **LAN/VPN** i jedną
   aplikację, np. Nextcloud. Kreator doda jej zależności i reverse proxy.
   VPN wymaga osobnej konfiguracji — kreator go nie instaluje.
3. Sprawdź logowanie, zapis pliku oraz [kopię i próbne odtworzenie](docs/backup-and-restore.md).
4. Dopiero potem rozważ [dostęp publiczny](docs/nginx-proxy.md) i [DDNS](docs/ddns.md).

## Szybki start

Wykonuj polecenia w terminalu **serwera z Linuksem**, jako zwykły użytkownik
z możliwością użycia `sudo`. Potrzebujesz Bash, Git i Python 3.10 lub nowszego
oraz połączenia z internetem. Kreator uruchamia Python przed instalacją Dockera.

Na Ubuntu/Debianie zainstaluj brakujące narzędzia:

```bash
sudo apt update
sudo apt install bash git python3 sudo
python3 --version
```

Przygotowanie systemu opisuje [poradnik Ubuntu Server, Docker i Cockpit](docs/ubuntu-docker-cockpit.md).
Kreator rozpoznaje Ubuntu/Debiana, Fedorę, RHEL (Rocky, Alma), Arch i openSUSE.
**Pełnego wdrożenia na czystym hoście nie potwierdzono testem od początku
do końca; testy jednostkowe nie zastępują takiej weryfikacji.**
Pozostałe rodziny opisano wraz z ograniczeniami w [dokumentacji kreatora](docs/homelab-wizard.md).

Pobierz repozytorium, przejrzyj kod oraz ograniczenia i uruchom kreator:

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

## Sprawdzenie pierwszego uruchomienia

W katalogu repozytorium wykonaj dla wybranej usługi (przykład Nextcloud):

```bash
cd containers/nextcloud
sudo docker compose ps
sudo docker compose logs --tail=100 nextcloud
```

Pierwszy start może potrwać kilka minut. Otwórz hostname zapisany przy
konfiguracji usługi. W LAN skonfiguruj lokalny DNS lub wpis w pliku hosts
na komputerze, z którego otwierasz stronę: nazwa ma wskazywać adres LAN serwera.
Tryb LAN/VPN nie zamawia publicznego certyfikatu HTTPS. Do pierwszego testu
użyj danych próbnych. Przy błędzie sprawdź nazwę, adres, logi i stan kontenerów
przed ponowną instalacją; nie usuwaj katalogu danych.

## Słownik na początek

- **Host** — komputer z Linuksem uruchamiający kontenery.
- **Stos Compose** — grupa współpracujących usług, np. aplikacja i jej baza.
- **Reverse proxy** — kieruje żądania do właściwej aplikacji według nazwy.
- **DNS** — wiąże nazwę, np. `cloud.home.arpa`, z adresem IP.
- **DDNS** — aktualizuje DNS po zmianie publicznego IP; nie omija CGNAT.
- **LAN / VPN** — sieć lokalna / prywatne połączenie do zdalnej sieci.
- **Wolumen lub podłączony katalog** — miejsce przechowywania danych
  niezależnie od odtwarzanego kontenera.
- **`.env`** — plik ustawień, często z hasłami; nie publikuj go.

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
trwałe są domyślnie w podkatalogu `data/` danej usługi; niektóre stosy
korzystają też z wolumenów Dockera lub konfigurowalnych ścieżek. Sprawdź
sekcję `volumes` swojego Compose. Dane i lokalne sekrety nie trafiają do Git.

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
