# Osobne stosy Docker Compose

Ta instrukcja dotyczy starszych, ręcznych przykładów w `stacks/`. Do nowego
wdrożenia zalecany jest kreator i konfiguracje w `containers/`; nie uruchamiaj
obu wariantów jednocześnie, ponieważ używają tych samych nazw kontenerów i
portów.

Każda usługa ma własny katalog w [`stacks/`](../stacks/). To celowy podział:
niezależne cykle aktualizacji, urządzenia USB i tryb host Home Assistant nie
pasują do jednego wspólnego Compose. Bazy, dane aplikacji i niewebowe
protokoły pozostają odseparowane.

## Pierwsze uruchomienie

Wymagany jest Docker Compose v2. Polecenia w przykładach wykonuj z katalogu
repozytorium lub stosu wskazanego przez `cd`. Najpierw sprawdź konfigurację,
ustaw sekrety/ścieżki w `.env`, a dopiero potem uruchom usługę:

```bash
cd stacks/reverse-proxy
cp .env.example .env
docker compose config --quiet
docker compose up -d
```

Proxy tworzy wspólną sieć `homelab-proxy`. Uruchamiaj go przed stosami
webowymi. W pozostałych katalogach skopiuj `.env.example` (jeśli występuje)
do `.env`, popraw wartości i uruchom `docker compose config --quiet` oraz
`docker compose up -d`. Przykładowo:

```bash
cd ../wordpress
cp .env.example .env
# Edytuj .env: unikalne hasła i prawdziwy hostname.
docker compose config --quiet
docker compose up -d
```

Katalogi `data/`, `.env` i pliki stanu kontenerów nie są wersjonowane.
Compose może utworzyć je z uprawnieniami niepasującymi do użytkownika
kontenera; sprawdź wymagane UID/GID w dokumentacji obrazu.

### MQTT i Zigbee2MQTT

Mosquitto jest skonfigurowany bez anonimowego dostępu. Przed pierwszym
uruchomieniem utwórz plik haseł w `stacks/mqtt/config/`:

```bash
cd stacks/mqtt
docker run --rm -it --user 0:0 \\
  -v "$PWD/config:/mosquitto/config" \\
  --entrypoint mosquitto_passwd eclipse-mosquitto:2 \\
  -c /mosquitto/config/passwd mqttuser
sudo chown 1883:1883 config/passwd
sudo chmod 640 config/passwd
sudo install -d -o 1883 -g 1883 data
docker compose config --quiet
docker compose up -d
```

W stosie Zigbee2MQTT skopiuj `.env.example`, ustaw ścieżkę `/dev/serial/by-id`
i uruchom usługę. Kreator z `containers/` dodatkowo sprawdza, czy wskazano
istniejące urządzenie znakowe. Pierwszą konfigurację koordynatora i brokera MQTT wykonaj
w kreatorze Zigbee2MQTT; jako adres brokera użyj `mqtt://mqtt:1883`, a dane
logowania zgodne z utworzonym kontem. Home Assistant używa host networking,
więc z jego integracji MQTT łączy się do `127.0.0.1:1883` na hoście. Pamiętaj,
że MQTT jest dostępne lokalnie na serwerze, nie zdalnie.

### Dane logowania i urządzenia

- WordPress, Euro-Office, Samba i WUD wymagają własnego `.env` z unikalnymi
  hasłami. Dla Euro-Office użyj co najmniej 32 losowych znaków dla JWT i
  wpisz ten sam sekret w aplikacji Nextcloud Office.
- Minecraft pozostaje wyłączony przez `MINECRAFT_EULA=FALSE`, dopóki
  administrator świadomie nie zaakceptuje EULA i nie zmieni wartości na
  `TRUE`. Ustaw whitelistę oraz adres LAN serwera w bindowaniu portu.
- Zigbee2MQTT wymaga fizycznego koordynatora. Nie kopiuj przykładowej
  ścieżki urządzenia bez ustalenia własnego stabilnego `/dev/serial/by-id`.
- Samba i Jellyfin korzystają z lokalnego katalogu mediów, ale tylko Samba
  ma zapis; Jellyfin montuje bibliotekę read-only. Sprawdź właściciela
  plików i prawa dostępu przed startem.

## Nazwy domen i certyfikaty

Webowe stosy mają zmienne `VIRTUAL_HOST`, `VIRTUAL_PORT` i
`LETSENCRYPT_HOST`. Domyślnie nazwy są puste, więc przykłady nie generują
ruchu ani żądań certyfikatów dla fikcyjnych domen. W pliku `.env` danego
stosu ustaw prawdziwy hostname dopiero wtedy, gdy rekord DNS wskazuje na
serwer i porty są osiągalne. Ustaw też `LETSENCRYPT_EMAIL` w
`stacks/reverse-proxy/.env`.

Przykładowy stos używa `acme-companion`, który jest zintegrowany z
`nginx-proxy` i automatyzuje wydawanie/odnawianie certyfikatów. Nie uruchamiaj
równolegle Certbota i `acme-companion` do tych samych nazw — dwa klienty ACME
mogłyby nadpisywać lub niezależnie odnawiać te same certyfikaty. Jeśli
wybierzesz Certbota, zastąp companion osobną, przetestowaną konfiguracją
webroot i hookiem kopiującym certyfikaty/reloadującym proxy; ten przykład
nie uruchamia Certbota.

Nextcloud i Immich są zdefiniowane w głównym `compose.yaml`. Żeby podłączyć
je do tego samego proxy, uruchom Compose z dodatkowym override:

```bash
# Uruchom z katalogu głównego repozytorium; nie nadpisuj istniejącego .env.
test -f .env || cp .env.example .env
# Ustaw sekrety oraz NEXTCLOUD_HOST/IMMICH_HOST i LETSENCRYPT_EMAIL.
docker compose --env-file .env -f compose.yaml \\
  -f stacks/reverse-proxy/nextcloud.override.yaml config --quiet
docker compose --env-file .env -f compose.yaml \\
  -f stacks/reverse-proxy/nextcloud.override.yaml up -d
```

Do Immich dodaj `--profile photos` do obu poleceń. Zachowuje to obecny
samodzielny start Nextcloud/Immich bez reverse proxy. Samo ustawienie domeny
nie konfiguruje DNS, port-forwardingu, `trusted_domains`, zaufanych proxy
ani ustawień URL aplikacji. Skonfiguruj je zgodnie z dokumentacją konkretnej
aplikacji. Certyfikaty HTTP-01 wymagają publicznie osiągalnego portu 80;
CGNAT może uniemożliwić takie połączenie.

## Co trafia przez proxy

| Stos | Dostęp i routing |
|---|---|
| Nextcloud, Immich | HTTP przez `nginx-proxy` po użyciu override; lokalne porty pozostają związane z `127.0.0.1`. |
| WordPress, Jellyfin, Zigbee2MQTT, Euro-Office | HTTP przez wspólną sieć `homelab-proxy`; hosty i TLS są opcjonalne. Kreator nie wystawia panelu administracyjnego Zigbee2MQTT publicznie. |
| Home Assistant | Domyślnie `network_mode: host` dla discovery, więc port 8123 należy ograniczyć firewallem do LAN/VPN. Proxy wymaga osobnej konfiguracji upstream do hosta oraz ustawień `trusted_proxies` w Home Assistant. |
| MQTT / Mosquitto | MQTT/TCP, nie HTTP; port 1883 jest domyślnie związany wyłącznie z loopback hosta. Nie dodawaj go do nginx-proxy. |
| Samba | SMB/TCP; wystaw wyłącznie w zaufanej sieci lokalnej. Reverse proxy HTTP nie obsługuje SMB. |
| Minecraft | Port gry TCP; ustaw bindowanie do adresu LAN, whitelistę i świadome reguły routera/firewalla. |
| WUD (updater) | Panel tylko na loopback; dostęp zdalny wyłącznie przez VPN/tunel administracyjny. Nie wystawiaj publicznie. |

`nginx-proxy` obserwuje metadane Dockera przez socket i generuje konfigurację
na podstawie zmiennych kontenerów, a nie statycznych bloków domen w pliku
`nginx.conf`. Montaż socketu Docker — nawet jako `:ro` — pozostaje
uprawnieniem wysokiego ryzyka. Uruchamiaj wyłącznie zaufane obrazy, ogranicz
hosty wystawiane do Internetu i sprawdź ekspozycję portów z zewnętrznej sieci.

Nie uruchamiaj jednocześnie kilku kontenerów próbujących zająć hostowe porty
80/443. W przypadku aktualizacji nie używaj ślepo `latest`: przypnij
przetestowaną wersję obrazu i wykonaj kopię danych aplikacji oraz baz.
