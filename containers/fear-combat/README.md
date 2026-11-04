# F.E.A.R. Combat SEC2

Serwer gry sieciowej, uruchamiany bez interfejsu graficznego. Ten wariant
odwzorowuje układ działającego kontenera autora: Ubuntu 24.04, 32-bitowy
Linux Dedicated Server i biblioteka SEC2 2.2.2 A1. Wymaga hosta x86-64
(Linux/amd64); ARM nie jest tutaj zweryfikowany.

Repozytorium zawiera przepis na obraz i konfigurację, a pliki gry przygotowujesz
lokalnie. Nie zawiera binariów, danych graczy, kluczy ani produkcyjnych haseł.
Nowy zestaw ze startera wymaga testu połączenia z klienta gry.

## 1. Przygotuj pliki gry

Pracuj w `containers/fear-combat/`. Potrzebny jest pełny Linux Dedicated
Server, nie sama aktualizacja SEC2. Źródła wykorzystane na serwerze autora:

- [FEAR Server — opis i pakiety społeczności](https://fear-combat.nl/FEAR-Server.html)
- [Pakiet Linux 1.10](https://fear-combat.nl/downloads/FEAR_Server_1.10_Linux.tar.gz)
- [Aktualizacja SEC2 Linux](https://cpp.mx/files/SEC2/Unstable/SEC2_2.2.2.910.L.zip)
- [Społeczność FEAR Combat](https://fear-community.org/)

To źródła społecznościowe. Ich dostępność i zgodność zmieniają się;
w czasie przygotowania startera nie potwierdzono ponownego pobrania archiwów.
Dokumentacja społeczności zawiera również starszą informację o problemach
z wersją Linux. Ten wariant opiera się na sprawdzonej konfiguracji autora,
a nie na założeniu, że każdy pakiet SEC2 zadziała tak samo.

Sumy zapisane w dokumentacji działającej instalacji autora:

| Plik | SHA-256 |
|---|---|
| `FEAR_Server_1.10_Linux.tar.gz` | `61b8cce3376ccb78167e803092bfdbb9a3787c617b47055698cdd7bf36a9a489` |
| `libGameServer.so` po aktualizacji SEC2 | `2ece65438d07b08cfc0aaa3c8ebc28eb1efb42379f8c48946efba8b5a5cbc7a2` |

Druga suma dotyczy biblioteki, nie całego ZIP. Zweryfikuj pliki przez
`sha256sum NAZWA_PLIKU` i zapoznaj się z warunkami ich użycia.
Nie uruchamiaj przypadkowych binariów z innych źródeł.

Umieść pełną zawartość katalogu FEAR z pakietu w `server/FEAR/`:
`fearserver.bin`, biblioteki silnika, zasoby i dokumentację. Zastąp
`server/FEAR/libGameServer.so` biblioteką z właściwej aktualizacji Linux.
Zachowaj oryginalną dokumentację pakietu. Układ ma wyglądać tak:

```text
server/FEAR/fearserver.bin
server/FEAR/libGameServer.so
server/FEAR/...pozostałe pliki pakietu...
server/user/
config/ServerOptions.txt
```

## 2. Ustawienia

```bash
cp .env.example .env
chmod 600 .env
cp config/ServerOptions.example.txt config/ServerOptions.txt
mkdir -p server/user
chmod +x server/FEAR/fearserver.bin
id -u
id -g
```

W `.env` wpisz wyniki `id -u` i `id -g` jako `FEAR_UID` i `FEAR_GID`.
Katalog `server/user` musi być zapisywalny dla tego konta, a pliki gry
i konfiguracja czytelne. Nie stosuj `chmod 777`.

Domyślnie `FEAR_BIND_ADDRESS=127.0.0.1`. Aby grać z innego komputera,
wpisz adres LAN interfejsu serwera. `FEAR_PORT` to port hosta; port
wewnątrz kontenera i w `ServerOptions.txt` pozostaje `27888`.

Szablon `ServerOptions.example.txt` ma tryb Deathmatch, do 8 graczy,
dwie mapy i `LANOnly=1`. Zmieniaj lokalny `ServerOptions.txt`; nie publikuj
haseł w szablonie. Dostęp publiczny wymaga świadomej zmiany `LANOnly=0`
oraz konfiguracji routera i zapory. Zdalne komendy administracyjne
pozostają wyłączone przez `AllowScmdCommands=0`.

## 3. Uruchomienie

Po przygotowaniu plików wybierz `fear-combat` w kreatorze `bash ./homelab`
uruchomionym z katalogu głównego repo. Kreator sprawdzi pliki, zapyta o
adres LAN i port, ustawi UID/GID bieżącego konta oraz utworzy katalog danych
i lokalną konfigurację, jeśli ich jeszcze nie ma. Zachowa istniejącą konfigurację.

Możesz też uruchomić usługę ręcznie, w katalogu `containers/fear-combat/`:

```bash
sudo docker compose config --quiet
sudo docker compose up -d --build
sudo docker compose ps
sudo docker compose logs --tail=100 server
```

W logach działającego serwera oczekuj komunikatu `Ready`. Następnie
sprawdź połączenie z klienta F.E.A.R. Combat zgodnego z SEC2 używaną
na serwerze. Sam stan „running” kontenera nie potwierdza działania gry.

## Sieć i dane

- Serwer używa UDP, domyślnie `27888`; nie korzysta z HTTP reverse proxy,
  certyfikatów Let's Encrypt ani sieci `homelab-proxy`.
- Kreator może dodać regułę UDP dla podanej zaufanej podsieci LAN.
  Nie otwiera gry publicznie i nie zmienia routera.
- Dla dostępu z internetu przekieruj wyłącznie wybrany port UDP hosta.
  Sprawdź osiągalność także poza domowym Wi-Fi i uwzględnij reguły Dockera.
- Pliki gry są montowane tylko do odczytu. Zapisy trafiają do `server/user/`.
  Kopię tego katalogu i lokalnej konfiguracji wykonuj przy zatrzymanej usłudze:
  `sudo docker compose stop server`, kopia, `sudo docker compose start server`.
- Zachowaj również użyte binaria i wersję biblioteki SEC2 w prywatnej kopii.
  Odtwarzanie wymaga tych samych plików, ustawień i właściciela danych.
- Brak plików wejściowych zatrzymuje wdrożenie z komunikatem; kreator nie
  pobiera ich automatycznie i nie zastępuje konfiguracji działającego serwera.

Zobacz [opis homelaba i serwerów gier](https://master-homelab.pl/homelab/domowy-homelab-z-dockerem-i-kontenerami-jak-dziala-moj-serwer/).
