# Pełna mapa homelaba

Pełny homelab to nie tylko Nextcloud i Immich. Obejmuje host i pamięć masową,
sieć wejściową, chmurę, automatykę, multimedia, stronę WWW, udostępnianie
plików, gry oraz utrzymanie. Główny `compose.yaml` uruchamia Nextcloud,
a Immich jest profilem opcjonalnym. Kreator korzysta z aktualnych konfiguracji
w [`containers/`](../containers/); starsze, ręczne przykłady są w
[`stacks/`](../stacks/). Nie uruchamiaj obu układów jednocześnie ani
wszystkiego naraz bez dostosowania ścieżek, sekretów, urządzeń i reguł sieci.

## Host, administracja i dane

| Warstwa | Usługa / rola | Zasady i źródła |
|---|---|---|
| System | Ubuntu Server LTS | [Pobieranie Ubuntu Server](https://ubuntu.com/download/server), [dokumentacja](https://ubuntu.com/server/docs/) |
| Kontenery | Docker Engine + Compose | Instaluj z [oficjalnego repozytorium Dockera](https://docs.docker.com/engine/install/ubuntu/); nie publikuj demona Docker na TCP. |
| Panel hosta | Cockpit | [Instalacja i użycie](https://cockpit-project.org/running.html); ogranicz `9090/tcp` do LAN/VPN. |
| Firewall | UFW + reguły/router dla Docker | UFW nie filtruje automatycznie każdego opublikowanego portu Dockera; zobacz [poradnik Ubuntu/Docker](ubuntu-docker-cockpit.md). |
| Dane | Dyski w RAID | W tym homelabie dane są przechowywane na macierzy RAID, aby ograniczyć przestój przy awarii dysku. Dokładny poziom RAID i liczba dysków zależą od konkretnej konfiguracji; nie należy ich zgadywać na podstawie samego punktu montowania. |
| Kopie | Kopia poza macierzą | RAID nie jest kopią zapasową. Utrzymuj osobną kopię na innym urządzeniu lub poza domem i testuj odtwarzanie. |

RAID zwiększa dostępność tylko w granicach odporności wybranego poziomu. Nie
chroni przed skasowaniem plików, ransomware, błędem administratora, kradzieżą,
pożarem ani awarią całej macierzy. Dyski RAID mogą też ulec awarii podczas
odbudowy. Zobacz [opis RAID i kopii zapasowych](storage-and-raid.md).

## Sieć, domeny i dostęp z Internetu

| Rola | Usługa / komponent | Zasady i źródła |
|---|---|---|
| Reverse proxy | Kontener `nginx-proxy` | [Repozytorium nginx-proxy](https://github.com/nginx-proxy/nginx-proxy); [przykładowy Compose](../stacks/reverse-proxy/compose.yaml); przyjmuje żądania HTTP/HTTPS i na podstawie domeny/subdomeny kieruje je do właściwego kontenera aplikacji. Wystawiaj tylko zaplanowane porty HTTP/HTTPS. |
| Certyfikaty | Let's Encrypt przez ACME | Certyfikaty można zautomatyzować przez [acme-companion](https://github.com/nginx-proxy/acme-companion) dla nginx-proxy albo konfigurować osobno przez [Certbot](https://certbot.eff.org/). Wybierz jeden spójny mechanizm zarządzania certyfikatami i odnowieniami. |
| DNS i router | Domena, rekordy DNS, NAT | Rekord DNS wskazuje domenę/subdomenę na adres serwera; dopiero `nginx-proxy` wybiera kontener docelowy. Publikuj tylko niezbędne porty. Nie wystawiaj Cockpit, SSH, SMB, MQTT, paneli administracyjnych ani baz danych do Internetu. |

### Stały publiczny adres IP lub DDNS

Zarówno stały publiczny adres IP, jak i DDNS mogą prowadzić do tego samego
układu z reverse proxy:

- **Stały publiczny adres IP:** rekord `A` domeny wskazuje na publiczny IPv4
  serwera/routera. Jeśli używasz publicznego IPv6, rekord `AAAA` wskazuje
  właściwy adres, a firewall IPv6 musi zezwalać tylko na potrzebny ruch.
  Stały adres ułatwia konfigurację DNS, ale sam nie otwiera dostępu.
- **Dynamiczny publiczny adres IP:** router lub klient DDNS na stale
  działającym urządzeniu wykrywa zmianę adresu i aktualizuje rekord DNS.
  Możesz użyć nazwy od dostawcy DDNS albo własnej domeny, jeśli operator
  DNS pozwala aktualizować jej rekordy/API. Chroń dane logowania/API klienta
  DDNS i nadaj im możliwie ograniczone uprawnienia.

W obu wariantach domena rozwiązuje się do adresu routera/serwera, a dopiero
potem router przekazuje wymagane porty do hosta i `nginx-proxy` routuje
żądanie do kontenera aplikacji. DDNS aktualizuje wyłącznie powiązanie nazwy
z adresem IP — **nie** konfiguruje przekierowania portów, firewalla, TLS ani
samego reverse proxy.

DDNS nie omija **CGNAT** ani blokady ruchu przychodzącego przez dostawcę
Internetu. Jeśli router nie ma własnego, osiągalnego publicznego adresu
(adres WAN może być prywatny lub z zakresu współdzielonego), zwykłe
przekierowanie portów może nie działać. Zapytaj ISP o publiczny IPv4,
skorzystaj z publicznego IPv6, jeśli sieć i klienci go obsługują, albo użyj
VPN/tunelu zewnętrznego. Zweryfikuj osiągalność z sieci zewnętrznej, a nie
tylko przez Wi-Fi w domu.

Źródła: [jak działa DDNS (No-IP)](https://www.noip.com/support/knowledgebase/what-is-dynamic-dns),
[aktualizacja dynamicznych rekordów DNS (Cloudflare)](https://developers.cloudflare.com/dns/manage-dns-records/how-to/managing-dynamic-ip-addresses/).

Przepływ wygląda w uproszczeniu tak:

```text
cloud.example.net
       │ DNS wskazuje adres serwera
       ▼
serwer:80/443 → kontener nginx-proxy
                    │ nagłówek Host / skonfigurowana domena
                    ▼
              kontener Nextcloud
```

W wariancie [`nginx-proxy`](https://github.com/nginx-proxy/nginx-proxy)
kontenery aplikacji dołączają do wspólnej sieci Docker z proxy i deklarują
obsługiwaną nazwę hosta (zwykle przez `VIRTUAL_HOST`). Kontener proxy
obserwuje metadane Dockera i generuje routing do właściwej usługi. To nie
jest serwer DNS: rekordy domeny, dostępność portów na routerze oraz reguły
firewalla trzeba skonfigurować oddzielnie. Szczegóły zmiennych i sieci
sprawdź w [dokumentacji nginx-proxy](https://github.com/nginx-proxy/nginx-proxy#usage).

Jeśli walidacja certyfikatu wymaga HTTP-01, port 80 musi być osiągalny podczas
walidacji; nie blokuj go pochopnie. TLS nie zastępuje aktualizacji, mocnych
haseł, kopii ani kontroli dostępu. Inne usługi dostępne z zewnątrz najlepiej
udostępniać przez VPN albo reverse proxy z poprawnym TLS.

## Pliki, zdjęcia i dokumenty

| Usługa | Rola | Oficjalne źródła |
|---|---|---|
| Nextcloud + PostgreSQL + Redis | Pliki, kalendarz i współpraca; aplikacja i baza powinny mieć własne kopie. | [Nextcloud](https://nextcloud.com/), [dokumentacja administracyjna](https://docs.nextcloud.com/server/latest/admin_manual/), [główny Compose](../compose.yaml) |
| Immich (opcjonalnie) | Zarządzanie zdjęciami i wideo. | [Immich](https://immich.app/), [dokumentacja i aktualny Compose](https://docs.immich.app/), [główny Compose](../compose.yaml) |
| Euro-Office / Nextcloud Office | Wspólna edycja dokumentów w Nextcloud; serwer Document Server jest usługą towarzyszącą Nextcloud, a nie samodzielnym dyskiem/chmurą. | [Dokumentacja Euro-Office](https://euro-office.github.io/documentation/), [instalacja](https://euro-office.github.io/documentation/installation/), [Office w Nextcloud](https://docs.nextcloud.com/server/latest/admin_manual/office/index.html), [przykładowy Compose](../stacks/euro-office/compose.yaml) |
| Samba (SMB) | Udostępnianie katalogów hosta urządzeniom w LAN. | [Dokumentacja Samba](https://wiki.samba.org/index.php/Main_Page), [przykładowy Compose](../stacks/samba/compose.yaml); zezwól tylko na zaufaną sieć i przypisz osobne konta/uprawnienia. |

Nextcloud, Immich, Euro-Office i udziały Samby mogą korzystać z tych samych
fizycznych dysków, ale nie należy bez planu montować tego samego katalogu do
wielu aplikacji z prawem zapisu. Ustal właściciela danych, uprawnienia,
strukturę katalogów oraz sposób kopii i przywracania dla każdej usługi.

## Automatyka domowa

| Usługa | Rola | Oficjalne źródła |
|---|---|---|
| Home Assistant | Automatyzacje, integracje i panel smart home. | [Home Assistant](https://www.home-assistant.io/), [instalacja Container na Linux/Docker](https://www.home-assistant.io/installation/linux/), [przykładowy Compose](../stacks/home-assistant/compose.yaml) |
| MQTT / Mosquitto | Broker komunikatów dla urządzeń i integracji. | [Eclipse Mosquitto](https://mosquitto.org/), [dokumentacja](https://mosquitto.org/documentation/), [przykładowy Compose](../stacks/mqtt/compose.yaml) |
| Zigbee2MQTT | Łączy koordynator Zigbee z MQTT i urządzeniami Zigbee. | [Zigbee2MQTT](https://www.zigbee2mqtt.io/), [instalacja Docker](https://www.zigbee2mqtt.io/guide/installation/02_docker.html), [przykładowy Compose](../stacks/zigbee2mqtt/compose.yaml) |

Home Assistant Container nie zawiera systemu dodatków dostępnego w Home
Assistant OS — broker MQTT i Zigbee2MQTT to osobne usługi. Zigbee2MQTT wymaga
kompatybilnego koordynatora USB lub sieciowego; zaplanuj jego stabilną ścieżkę,
uprawnienia i kopię konfiguracji. MQTT powinien wymagać uwierzytelnienia
i nie powinien być otwarty do Internetu.

## Strony WWW

| Usługa | Rola | Oficjalne źródła |
|---|---|---|
| WordPress | CMS dla strony lub bloga; zwykle potrzebuje własnej bazy danych i trwałego katalogu `wp-content`. | [WordPress](https://wordpress.org/), [instrukcja instalacji](https://developer.wordpress.org/advanced-administration/before-install/howto-install/), [oficjalny obraz Docker](https://hub.docker.com/_/wordpress), [przykładowy Compose](../stacks/wordpress/compose.yaml) |

WordPress powinien mieć osobną bazę i sekrety, regularne aktualizacje rdzenia,
wtyczek i motywów oraz kopię bazy i plików. Ruch webowy kieruj przez wspólny
reverse proxy; nie publikuj bez potrzeby dodatkowych portów aplikacji.

## Media i gry

| Usługa | Rola | Oficjalne źródła |
|---|---|---|
| Jellyfin | Strumieniowanie filmów, seriali i muzyki z katalogów biblioteki. | [Jellyfin](https://jellyfin.org/), [instalacja w Dockerze](https://jellyfin.org/docs/general/installation/container/), [przykładowy Compose](../stacks/jellyfin/compose.yaml) |
| Minecraft | Osobny serwer gry; obraz kontenera jest projektem społeczności, nie oficjalnym obrazem Mojang/Microsoft. | [Projekt itzg/docker-minecraft-server](https://github.com/itzg/docker-minecraft-server), [Minecraft EULA](https://www.minecraft.net/en-us/eula), [przykładowy Compose](../stacks/minecraft/compose.yaml) |

Montuj bibliotekę Jellyfin tylko do odczytu, jeśli aplikacja nie musi niczego
w niej zmieniać. Utrzymuj zapisywalne konfigurację, cache i bazę Jellyfin
osobno. Serwer Minecraft ma własny świat i kopie zapasowe; użyj whitelisty
i wystawiaj tylko wymagany port gry. Nie udostępniaj portów RCON ani konsoli
administracyjnej publicznie.

## Utrzymanie i aktualizacje

| Rola | Usługa / metoda | Źródła i uwagi |
|---|---|---|
| Monitoring wydań | What's Up Docker? (WUD) lub podobny updater | [Repozytorium WUD](https://github.com/getwud/wud), [przykładowy Compose](../stacks/wud/compose.yaml). Najpierw monitoruj i powiadamiaj; automatyczne podmienianie obrazów baz, Nextcloud, Immich czy WordPress bez kopii/testu może spowodować awarię lub utratę danych. |
| Aktualizacje systemu | APT / aktualizacje bezpieczeństwa Ubuntu | Weryfikuj po aktualizacji stan hosta, Docker, usługi i odtwarzanie kopii. |
| Kopie i odtwarzanie | Osobna procedura dla każdej usługi | [Kopie Nextcloud i Immich](backup-and-restore.md); sprawdzaj odtworzenie, nie tylko powstanie plików. |

Updater potrzebuje dostępu do informacji o działających kontenerach. Dostęp
do `/var/run/docker.sock` jest równoważny bardzo wysokim uprawnieniom na
hoście — ogranicz go, zabezpiecz panel WUD i nie włączaj automatycznych
aktualizacji wszystkich kontenerów bez wyjątków i planu powrotu.

## Własne projekty

KADR i Planszownia pozostają odrębnymi projektami i nie są kopiowane ani
uruchamiane przez ten starter. Nie publikuj ich konfiguracji prywatnej,
sekretów, produkcyjnych baz ani domen. Jeśli zdecydujesz się opisać je w mapie,
dodaj jedynie neutralne role usług i linki do repozytoriów, do których
czytelnicy mają dostęp.

## Zasady podziału stosów

Nie umieszczaj całego homelaba w jednym Compose. Grupuj usługi według
zależności i cyklu życia, na przykład:

1. reverse proxy i certyfikaty;
2. Nextcloud z własną bazą i Redis;
3. Immich z własną bazą i Valkey;
4. Home Assistant, broker MQTT i Zigbee2MQTT;
5. WordPress z osobną bazą;
6. Jellyfin i serwer Minecraft;
7. współdzielone pliki i narzędzia utrzymaniowe.

Każdy stos powinien mieć własne dane trwałe, sekretne `.env`, ograniczone
porty i opisaną kopię zapasową. Bazy i panele administracyjne pozostaw w
wewnętrznych sieciach Compose, jeśli inne usługi nie muszą się z nimi łączyć.
Przed użyciem sprawdzaj oficjalną dokumentację wersji, której faktycznie
używasz; pliki `main`/`latest` z Internetu nie zawsze pasują do wydania.
Przykłady wdrożeniowe, sieci wspólne i konfiguracja proxy są opisane w
[instrukcji osobnych stosów Compose](compose-stacks.md).
