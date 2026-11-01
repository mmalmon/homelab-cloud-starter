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

## Kolejność pytań

1. Instalacja Docker Engine, Compose v2 i Cockpit, jeśli ich brakuje.
2. Dostęp sieciowy: LAN/VPN, stały publiczny IP albo DDNS (domyślnie to, co
   zapisano poprzednio w `containers/nginx-proxy/.env`).
3. Lista usług wykrytych w `containers/` — kreator oznacza już
   skonfigurowane, a Enter wybiera tylko nowe.
4. Adres LAN, hostnames wybranych usług, e-mail Let's Encrypt, ustawienia
   usług (np. SMTP Updatera), opcjonalny klient DDNS, firewall i uruchomienie.

Lista usług powstaje z katalogów `containers/<nazwa>/` zawierających
`compose.yaml` i `wizard.json`, więc nowy kontener pojawia się w kreatorze bez
zmian w kodzie (zob. [containers/README.md](../containers/README.md)).
Przy dodawaniu usługi później kreator ponownie zapisuje `nginx-proxy` z
domenami nowej usługi.

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
3. **DDNS:** podaj hostnames od swojego dostawcy. Kreator może dodatkowo
   zainstalować na hoście klienta `ddclient` lub `inadyn` (DuckDNS, Cloudflare,
   No-IP) albo pominąć ten krok, gdy DDNS działa w routerze. Szczegóły i
   wymagania routera opisuje [DDNS](ddns.md). Kontenerów DDNS nie ma.

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
- Dostęp do Docker socketu w `nginx-proxy` jest bardzo uprzywilejowany.
  Używaj zaufanych obrazów. Aktualizacje kontenerów opisuje
  [Updater](../containers/updater/README.md) — kreator instaluje go jako usługę `updater`: pyta o SMTP, ustawia hasło
  zatwierdzania i harmonogram systemd (zob. sekcję „Updater” poniżej).
- Pliki `.env` zawierają sekrety i są ustawiane jako `600`; nigdy nie
  publikuj ich, nie dodawaj do zgłoszeń i nie wklejaj do logów.
- Kreator nie konfiguruje konta u dostawcy DDNS, publicznych DNS dla
  stałego adresu, przekierowań portów routera, klienta DDNS w routerze (kreator może tylko zainstalować klienta na hoście),
  weryfikacji domeny ani poprawnych ustawień reverse proxy wewnątrz aplikacji.
- Minecraft pozostaje wyłączony, dopóki administrator nie zaakceptuje EULA.
  Kreator wymaga jawnego potwierdzenia i whitelisty.
- Kreator nie usuwa usług ani danych. Zmiany w istniejących usługach wykonuj
  ręcznie po kopii zapasowej; obecnie tryb ponownego uruchomienia jest
  przeznaczony do dodawania stosów.

Instrukcje obsługi poszczególnych Compose i zależności między usługami są w
[katalogu kontenerów](../containers/README.md). Sprawdź oficjalne dokumentacje
[Dockera](https://docs.docker.com/engine/install/) i [Cockpit](https://cockpit-project.org/running.html).

## Updater

Wybór `updater` konfiguruje `containers/updater/.env` i uruchamia
`updater-web` za `nginx-proxy`. Kreator pyta o hostname, serwer SMTP,
szyfrowanie (`starttls`/`ssl`), port, adres odbiorcy i nadawcy oraz login i
hasło SMTP (bez echa; puste pole SMTP = wiadomości tylko w `state/outbox/`).
Następnie wywołuje `updater.py set-password` (hasło zatwierdzania, min. 12
znaków), opcjonalnie `test-mail` i instaluje timery systemd:
`homelab-updater-apply.timer` (co minutę) oraz `homelab-updater-check.timer`
(codziennie ok. 04:30), uruchamiane jako Twoje konto. Sekrety trafiają tylko
do lokalnego `.env` (`600`) i `state/`, które są ignorowane przez Git.
