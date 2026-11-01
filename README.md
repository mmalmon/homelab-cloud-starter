# Homelab Cloud Starter

Przykładowy, możliwie prosty start własnej chmury na Docker Compose:

- **Nextcloud** — pliki, kalendarz i współpraca;
- **PostgreSQL + Redis** — osobne usługi dla Nextcloud;
- **Immich (opcjonalnie)** — zdjęcia i wideo, uruchamiane profilem Compose.

Konfiguracja jest szablonem: nie zawiera ustawień konkretnego serwera, prywatnych domen, adresów IP ani danych dostępowych. **Nie jest gotowa do wystawienia do Internetu bez dodatkowego reverse proxy, TLS, zapory i kopii zapasowych.**

## Wymagania

- Linux lub inny host z Docker Engine;
- Docker Compose v2 (`docker compose`);
- dla zdjęć: wolne miejsce na bibliotekę oraz bazę Immich.

## Pełny homelab i źródła

Starter uruchamia Nextcloud i opcjonalnie Immich, ale pełny homelab może
obejmować również reverse proxy i TLS, Home Assistant z MQTT i Zigbee2MQTT,
WordPress, Jellyfin, Euro-Office, Sambę, Minecraft oraz monitoring aktualizacji.
Rola tych usług, wymagania sieciowe, RAID/kopie zapasowe i linki do oficjalnych
dokumentacji są zebrane w [pełnej mapie homelaba](docs/homelab-map.md).
Reverse proxy [`nginx-proxy`](docs/nginx-proxy.md) działa jako kontener:
DNS wskazuje serwer, a proxy kieruje żądanie domeny/subdomeny do właściwej
usługi webowej w Dockerze.

Kreator korzysta z osobnych konfiguracji w [`containers/`](containers/).
Starsze, ręczne przykłady w [`stacks/`](stacks/) oraz główny `compose.yaml`
pozostają dla porównania i prostego startu Nextcloud/Immich — nie uruchamiaj
ich równolegle z nowymi stosami, bo mogą używać tych samych nazw kontenerów i
portów. [Instrukcja uruchamiania stosów](docs/compose-stacks.md) wyjaśnia
starszy układ, wspólną sieć proxy i ograniczenia sieciowe.
Nie wszystkie usługi mogą lub powinny być kierowane przez reverse proxy:
Samba, MQTT i Minecraft używają innych protokołów, a Home Assistant działa
w trybie host.

Przed instalacją sprawdź źródła producentów: [Nextcloud](https://nextcloud.com/)
i jego [dokumentację](https://docs.nextcloud.com/server/latest/admin_manual/),
[Immich](https://immich.app/) i jego [dokumentację](https://docs.immich.app/),
a także dokumentację programu, którego wdrażasz. Konfiguracje w `stacks/` są
niezależnymi przykładami, a nie jednym produkcyjnym wdrożeniem. Przed
uruchomieniem ustaw lokalne ścieżki, hasła, urządzenia i porty zgodnie ze
swoim serwerem.

## Kreator homelaba

Na nowym hoście Ubuntu/Debian lub Fedora sklonuj repozytorium, przejrzyj
[ostrzeżenia i ograniczenia kreatora](docs/homelab-wizard.md), a następnie
uruchom:

```bash
git clone https://github.com/mmalmon/homelab-cloud-starter.git
cd homelab-cloud-starter
bash ./homelab
```

Kreator może zainstalować Docker Engine, Compose v2, Cockpit i skonfigurować
podstawowy firewall. Późniejsze uruchomienie `bash ./homelab` pozwala dodać kolejne
stosy bez nadpisywania istniejących sekretów. Kreator pyta o wybrane usługi,
domeny oraz statyczny publiczny adres IP albo DDNS (DuckDNS/Cloudflare), tworzy
lokalne pliki `.env` z uprawnieniami `600` i uruchamia tylko wybrane stosy.

Każda aplikacja ma osobny katalog w [`containers/`](containers/); główny
skrypt uruchamia [kreator](wizard/homelab_wizard.py). Usługi webowe są
dołączane do wspólnego `nginx-proxy`. Dockerfile nie jest dodawany dla
aplikacji używających gotowych obrazów upstream — katalog zawiera go tylko,
gdy serwis wymaga budowania własnego obrazu.

## Szybki start: Nextcloud

Przygotowujesz nowy serwer? Zacznij od poradnika
[Ubuntu Server + Docker + Cockpit + firewall](docs/ubuntu-docker-cockpit.md).

```bash
git clone https://github.com/mmalmon/homelab-cloud-starter.git
cd homelab-cloud-starter
cp .env.example .env
```

W `.env` ustaw **różne, losowe** hasła `NEXTCLOUD_ADMIN_PASSWORD`,
`NEXTCLOUD_DB_PASSWORD` i `IMMICH_DB_PASSWORD`. Przykładowe wartości wygenerujesz
poleceniem `openssl rand -hex 32`. Plik `.env` jest ignorowany przez Git.

Domyślnie Nextcloud nasłuchuje tylko na `127.0.0.1:8080`. Sprawdź konfigurację
i uruchom usługi:

```bash
docker compose config --quiet
docker compose pull
docker compose up -d
docker compose ps
```

Otwórz <http://localhost:8080>. Konto administratora powstaje z wartości
`NEXTCLOUD_ADMIN_USER` i `NEXTCLOUD_ADMIN_PASSWORD`.

Żeby używać Nextcloud z innego urządzenia w zaufanej sieci LAN, dodaj adres
serwera do `NEXTCLOUD_TRUSTED_DOMAINS` i rozważ reverse proxy. Jeśli
publikujesz port bezpośrednio, ustaw `BIND_ADDRESS` na adres LAN serwera,
nie na `0.0.0.0`, i pamiętaj, że porty Dockera mogą omijać reguły UFW.
Przeczytaj [poradnik firewalla](docs/ubuntu-docker-cockpit.md#3-firewall-ufw)
i sprawdź dostęp z innego urządzenia. Nigdy nie przekierowuj portu 8080
bezpośrednio z Internetu.

## Opcjonalnie: Immich

W `.env` ustaw `IMMICH_UPLOAD_LOCATION`, `IMMICH_DB_DATA_LOCATION` i
`IMMICH_DB_PASSWORD`, po czym uruchom profil zdjęć:

```bash
docker compose --profile photos config --quiet
docker compose --profile photos pull
docker compose --profile photos up -d
```

Immich będzie dostępny pod <http://localhost:2283>. Jego baza jest oddzielna
od bazy Nextcloud. Katalog uploadów zawiera dane zarządzane przez Immich —
**nie edytuj go ręcznie**. Dodatkowe, istniejące zdjęcia dodawaj przez funkcję
importu Immich, a nie przez zmianę zawartości biblioteki pod działającą usługą.

Compose dla Immich używa kanału `v3` dla serwera/ML i digestów dla bazy oraz
Valkey, według oficjalnego pliku wydania w chwili przygotowania szablonu.
Przed aktualizacją porównaj go z Compose bieżącego wydania w [oficjalnym
poradniku Immich](https://docs.immich.app/install/docker-compose/). Projekt
Immich ostrzega, że plik z gałęzi `main` może nie pasować do wydania.

## Dane i konfiguracja

Domyślnie dane są w `./data/`:

```text
data/
├── nextcloud/            # pliki aplikacji Nextcloud i katalog użytkownika
├── postgres/             # baza Nextcloud
└── immich/               # opcjonalne dane Immich i jego baza
```

Zmień lokalizacje w `.env`, zanim uruchomisz usługi. Bazy PostgreSQL powinny
być na lokalnym dysku, nie na NFS/SMB. `data/`, `.env` i kopie zapasowe są
ignorowane przez Git.

## Przydatne polecenia

```bash
docker compose ps
docker compose logs -f nextcloud
docker compose logs -f nextcloud-db
docker compose down             # zatrzymuje, ale nie usuwa danych
docker compose up -d
```

Przed aktualizacją lub zmianą ścieżek zrób i sprawdź kopię zapasową. Zobacz
[procedurę kopii i odtwarzania](docs/backup-and-restore.md) oraz
[zasady bezpieczeństwa](docs/security.md).

## Układ przykładowego homelaba

Zobacz [pełną mapę homelaba i źródła projektów](docs/homelab-map.md),
[poradnik Ubuntu Server, Docker i Cockpit](docs/ubuntu-docker-cockpit.md)
oraz [opis dysków RAID i kopii zapasowych](docs/storage-and-raid.md).
Niestandardowe aplikacje, w tym KADR i Planszownia, celowo pozostają odrębnymi
projektami — repozytorium nie kopiuje ani nie publikuje ich kodu.

## Wsparcie

To edukacyjny przykład, nie dystrybucja gotowego serwera. Przed użyciem
produkcyjnym dostosuj wersje obrazów, HTTPS, domeny, zaporę, politykę kopii
zapasowych i odzyskiwanie danych do swojego środowiska.
