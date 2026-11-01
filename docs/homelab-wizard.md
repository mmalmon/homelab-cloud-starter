# Kreator Homelaba

Uruchom `bash ./homelab` w sklonowanym repozytorium. Kreator działa interaktywnie
i dodaje wyłącznie wybrane stosy. Ponowne uruchomienie umożliwia dołączenie
nowych usług bez nadpisywania istniejących plików `.env`. Wygenerowane
konfiguracje są lokalne i nie są publikowane w Git.

Każda usługa ma osobny `containers/<nazwa>/compose.yaml` i `.env.example`.
Kreator uzupełnia `.env`, sprawdza `docker compose config`, tworzy wspólną
sieć proxy przez uruchomienie reverse proxy i uruchamia wybrane stosy. Do
większości usług upstream dostarcza gotowy obraz, dlatego Dockerfile nie jest
potrzebny. Przy wyborze Zigbee2MQTT podaj ścieżkę istniejącego koordynatora
z `/dev/serial/by-id/`. Wszystkie aktualne usługi oraz ich źródła są opisane w
[mapie homelaba](homelab-map.md).

## Instalacja hosta

Kreator wspiera automatyczną instalację na Ubuntu, Debianie i Fedorze:

- Docker Engine i plugin Docker Compose v2 pochodzą z oficjalnego
  repozytorium Dockera.
- Instaluje Cockpit i włącza gniazdo `cockpit.socket`.
- Na Ubuntu/Debianie instaluje UFW; na Fedorze korzysta z firewalld.
- Reguły firewalld przypisuje do strefy interfejsu używanego przez trasę LAN,
  a jeśli nie da się go ustalić — do strefy domyślnej.
- Nie dodaje użytkownika do grupy `docker`, ponieważ daje ona uprawnienia
  równoważne root. Jeśli polecenia Docker wymagają uprawnień, kreator użyje
  `sudo`.

Na innych dystrybucjach zainstaluj Docker Engine, Compose v2 i Cockpit ręcznie
zgodnie z oficjalną dokumentacją systemu. Kreator nadal może być użyty po
przygotowaniu tych narzędzi. Nie uruchamiaj go przez `curl | sh`; przejrzyj
sklonowany kod przed wykonaniem.

## Sieć, domeny i DDNS

Kreator oferuje trzy warianty:

1. **LAN/VPN:** lokalne hostnames z domyślną strefą `home.arpa`; skonfiguruj
   odpowiadające rekordy w lokalnym DNS/routerze. Nie są zamawiane publiczne
   certyfikaty.
2. **Publiczny stały IPv4:** podaj domenę i adres. Kreator zapisuje hostnames
   oraz pokazuje wymagane rekordy DNS. Rekordy statyczne trzeba utworzyć u
   operatora DNS samodzielnie.
3. **DDNS:** wybierz DuckDNS lub Cloudflare. Kreator zapisuje token do
   chronionego `.env`, tworzy odpowiedni osobny stos updatera i dodaje do
   niego hostnames wybranych aplikacji. Przy dodawaniu kolejnej usługi zachowuje
   już skonfigurowane hostnames i token. Token DuckDNS lub Cloudflare jest
   pytany bez wyświetlania na ekranie. Cloudflare powinien mieć osobny API
   token z ograniczonym dostępem `Zone:DNS:Edit`, a nie globalny klucz.

Dla publicznych hostnames kreator dołącza `acme-companion` do `nginx-proxy`
i ustawia `LETSENCRYPT_HOST`. Przed pierwszym startem ustaw DNS i router:
przekieruj tylko TCP `80/443` na LAN-owy adres serwera. HTTP-01 wymaga
osiągalnego portu 80; jeśli używasz rekordu AAAA, host musi być osiągalny po
IPv6.

Niektórzy dostawcy DDNS wymagają dodatkowej konfiguracji na routerze (np.
wbudowanego klienta DDNS z loginem i nazwą hosta). Kreator jej nie wykonuje;
sprawdź dokumentację dostawcy i modelu routera. DDNS nie omija CGNAT ani
blokad ISP. Sprawdź dostęp z zewnętrznej sieci.

Usługi webowe dostają własny wpis `VIRTUAL_HOST`, a publiczne również
`LETSENCRYPT_HOST`; `nginx-proxy` generuje routing dynamicznie z metadanych
Docker, więc nie trzeba edytować statycznego `nginx.conf`. Home Assistant,
MQTT, Samba i Minecraft korzystają z odrębnych protokołów/trybów sieciowych,
nie są publikowane pod subdomeną w reverse proxy. Panel Zigbee2MQTT jest
panelem administracyjnym: kreator udostępnia go przez proxy tylko w trybie
LAN/VPN, a w trybie publicznym pozostawia bez hosta i certyfikatu.

## Bezpieczeństwo i ograniczenia

- Kreator zmienia ustawienia systemowe/firewalla wyłącznie po potwierdzeniu.
  Podaj prawidłowy CIDR swojej zaufanej sieci LAN, aby ograniczyć Cockpit
  (`9090`), Home Assistant (`8123`), SMB (`445`) i lokalny port gry. SSH jest
  dopuszczane na wskazanym porcie, aby nie odciąć administracji.
- Docker może omijać UFW/firewalld dla opublikowanych portów. Samo
  `ufw allow/deny` nie jest pełną kontrolą ekspozycji kontenerów. Ogranicz
  bindowanie portów, skonfiguruj reguły `DOCKER-USER`/routera i sprawdź
  faktyczną osiągalność.
- Porty proxy są domyślnie związane z adresem LAN podanym w kreatorze, a nie
  z `0.0.0.0`. Sprawdź, czy router przekazuje publiczne porty do tego samego
  adresu. Nie wystawiaj Cockpit, Docker API/socketu, baz, SMB ani MQTT do
  Internetu.
- Dostęp do Docker socketu w `nginx-proxy` i WUD jest bardzo uprzywilejowany.
  Używaj zaufanych obrazów, nie wystawiaj panelu WUD publicznie, preferuj
  powiadomienia i ręczne aktualizacje.
- Pliki `.env` zawierają sekrety i są ustawiane jako `600`; nigdy nie
  publikuj ich, nie dodawaj do zgłoszeń i nie wklejaj do logów.
- Kreator nie konfiguruje konta Cloudflare/DuckDNS, publicznych DNS dla
  stałego adresu, przekierowań portów routera, klienta DDNS w routerze,
  weryfikacji domeny ani poprawnych ustawień reverse proxy wewnątrz aplikacji.
- Minecraft pozostaje wyłączony, dopóki administrator nie zaakceptuje EULA.
  Kreator wymaga jawnego potwierdzenia i whitelisty.
- Kreator nie usuwa usług ani danych. Zmiany w istniejących usługach wykonuj
  ręcznie po kopii zapasowej; obecnie tryb ponownego uruchomienia jest
  przeznaczony do dodawania stosów.

Instrukcje obsługi poszczególnych Compose i zależności między usługami są w
[dokumentacji stosów](compose-stacks.md). Sprawdź oficjalne dokumentacje
[Dockera](https://docs.docker.com/engine/install/), [Cockpit](https://cockpit-project.org/running.html),
[DuckDNS](https://github.com/linuxserver/docker-duckdns) i
[Cloudflare DDNS](https://github.com/favonia/cloudflare-ddns).
