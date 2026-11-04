# Kopia zapasowa i odtwarzanie

Kopia obejmuje bazę, pliki aplikacji i jej konfigurację. Co najmniej jedną
kopię trzymaj na innym urządzeniu lub poza domem. RAID i synchronizacja
plików nie zastępują kopii. O powodzeniu decyduje próbne odtworzenie.

## Nextcloud: zakres przykładu

Polecenia wykonuj w Bash na serwerze, w `containers/nextcloud/`.
Przykład dotyczy Compose z tego repo: `./data/nextcloud` zawiera aplikację,
konfigurację i pliki użytkowników, a `./data/postgres` — działającą bazę.
Nie ma tu zmiennej `APPDATA_ROOT`. Jeśli zmieniłeś montowania, używasz
zewnętrznego magazynu lub szyfrowania, uwzględnij również te dane i klucze.

## 1. Wykonanie kopii Nextcloud

Zarezerwuj przerwę w dostępie. Poniższe polecenia wykonuj kolejno; po błędzie
zatrzymaj się i sprawdź przyczynę. Katalog roboczy kopii jest na tym samym
hoście — gotowy zestaw trzeba potem przenieść poza serwer.

```bash
umask 077
BACKUP_DIR="$PWD/backups/$(date +%F-%H%M%S)"
mkdir -p "$BACKUP_DIR"
sudo docker compose exec -u www-data nextcloud php occ maintenance:mode --on
sudo docker compose stop nextcloud nextcloud-cron
sudo docker compose exec -T nextcloud-db \
  sh -c 'pg_dump --no-owner --no-acl -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  > "$BACKUP_DIR/nextcloud.sql"
sudo tar --acls --xattrs -C data -czf "$BACKUP_DIR/nextcloud-files.tar.gz" nextcloud
cp compose.yaml .env "$BACKUP_DIR/"
sudo docker compose images > "$BACKUP_DIR/images.txt"
sudo docker compose config --images > "$BACKUP_DIR/image-references.txt"
chmod 600 "$BACKUP_DIR/.env"
sudo docker compose start nextcloud
sudo docker compose exec -u www-data nextcloud php occ maintenance:mode --off
sudo docker compose start nextcloud-cron
```

Zatrzymanie aplikacji i crona zapobiega zapisom podczas kopiowania; baza
pozostaje uruchomiona na czas zrzutu. Nie kopiuj jej aktywnego katalogu
`data/postgres` jako zamiennika zrzutu SQL.

Jeśli kopiowanie się nie powiedzie, nie traktuj częściowego zestawu jako
gotowej kopii. Po sprawdzeniu stanu uruchom aplikację, wyłącz tryb
konserwacji i uruchom cron trzema ostatnimi poleceniami.

Sprawdź zestaw:

```bash
test -s "$BACKUP_DIR/nextcloud.sql"
sudo tar -tzf "$BACKUP_DIR/nextcloud-files.tar.gz" > /dev/null
(cd "$BACKUP_DIR" && sudo sha256sum nextcloud.sql nextcloud-files.tar.gz compose.yaml .env images.txt image-references.txt > SHA256SUMS)
```

Każde polecenie musi zakończyć się bez błędu. Przenieś cały katalog kopii
na niezależny nośnik, chroniąc dostęp i szyfrując transfer oraz magazyn.
Pliki `.env`, SQL i archiwum zawierają sekrety lub prywatne dane.
Zachowaj wersje obrazów z chwili kopii; dla zmiennych tagów zapisz również
identyfikatory RepoDigests (`sudo docker image inspect NAZWA_OBRAZU`).
Przed odtworzeniem zapewnij dostęp do tych samych obrazów.

## 2. Próbne odtworzenie na osobnym hoście

Ten przykład służy wyłącznie do **nowej maszyny testowej bez instalacji
Nextcloud i bez katalogu `data`**. Nie wykonuj go na działającym serwerze.
Stałe nazwy kontenerów w Compose wykluczają prostą izolację samą nazwą projektu.
Ogranicz test do LAN, wyłącz wysyłkę poczty i integracje zewnętrzne na czas
testu oraz nie podłączaj klientów synchronizacji do odtworzonej instancji.

1. Przygotuj Docker Engine i Compose. Skopiuj zestaw kopii do dostępnego
   tylko dla administratora katalogu na maszynie testowej. Utwórz osobny
   katalog roboczy i przejdź do niego.
2. Ustaw poniżej **rzeczywistą bezwzględną ścieżkę** do zestawu. Zachowaj
   `.env` i Compose z kopii; dobierz te same wersje Nextcloud i PostgreSQL,
   które działały podczas tworzenia kopii. Nie aktualizuj aplikacji
   w trakcie odzyskiwania.

```bash
BACKUP_DIR="/sciezka/do/zestawu-kopii"
(cd "$BACKUP_DIR" && sudo sha256sum -c SHA256SUMS)
test ! -e data
```

Jeśli weryfikacja zgłosi błąd lub katalog `data` istnieje, przerwij.
Po pomyślnym sprawdzeniu:

```bash
umask 077
cp "$BACKUP_DIR/compose.yaml" "$BACKUP_DIR/.env" .
chmod 600 .env
mkdir data
sudo tar --acls --xattrs --numeric-owner -xzf "$BACKUP_DIR/nextcloud-files.tar.gz" -C data
sudo docker network create homelab-proxy
sudo docker compose up -d nextcloud-db nextcloud-redis
sudo docker compose ps
```

Sieć `homelab-proxy` jest wymagana przez ten Compose. Jeśli już istnieje na
maszynie testowej, sprawdź jej przeznaczenie i pomiń jej tworzenie.
Poczekaj, aż baza i Redis mają stan `healthy`; do tego czasu nie importuj danych.
Nowy katalog bazy zawiera pustą bazę utworzoną ze zmiennych `.env`.

```bash
sudo docker compose exec -T nextcloud-db \
  sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  < "$BACKUP_DIR/nextcloud.sql"
sudo docker compose up -d nextcloud
sudo docker compose exec -u www-data nextcloud php occ status
sudo docker compose exec -u www-data nextcloud php occ maintenance:mode --off
sudo docker compose up -d nextcloud-cron
```

Nie kontynuuj po błędzie importu. Sprawdź logi i wersje przed ponowną próbą;
nie importuj drugi raz do częściowo wypełnionej bazy. Zachowaj oryginalną kopię.

## 3. Sprawdzenie odtworzonej aplikacji

- `sudo docker compose ps` pokazuje działające usługi, a `occ status`
  potwierdza instalację i wyłączony tryb konserwacji.
- Sprawdź `sudo docker compose logs --tail=100 nextcloud nextcloud-db`.
- Dla testu przez SSH z komputera klienckiego zestaw tunel:
  `ssh -L 18080:127.0.0.1:8080 UZYTKOWNIK@ADRES_TESTOWEGO_SERWERA`.
  Port `8080` zastąp wartością `NEXTCLOUD_PORT` z kopii.
  Otwórz `http://localhost:18080`; ewentualne przekierowania HTTPS lub
  trusted domains dostosuj **tylko w kopii testowej**, zgodnie z dokumentacją
  Nextcloud. Nie zmieniaj produkcyjnego DNS.
- Zaloguj się kontem z kopii, pobierz kilka plików, sprawdź ich zawartość,
  udostępnienia i aplikacje. Dodaj plik próbny i ponownie go pobierz.
- Zapisz datę testu, użyte wersje, wynik i czas odtwarzania. Sam poprawny
  import SQL nie dowodzi, że wszystkie dane są dostępne.

Przy rzeczywistym odzyskiwaniu starszej kopii przeanalizuj także
`maintenance:data-fingerprint` i wpływ na synchronizujących klientów.
Nie uruchamiaj tego polecenia automatycznie w każdym teście.

## Immich

Zachowaj bazę, pełną lokalizację `IMMICH_UPLOAD_LOCATION`, ustawienia
Compose i `.env` oraz wersje obrazów. Biblioteki zewnętrzne wymagają osobnej
kopii. Odtwarzanie Immich wykonuj według instrukcji zgodnej z zapisaną
wersją — procedura Nextcloud powyżej nie jest procedurą dla Immich.

## Oficjalne instrukcje

- [Nextcloud: kopia zapasowa](https://docs.nextcloud.com/server/latest/admin_manual/maintenance/backup.html)
- [Nextcloud: odtwarzanie i synchronizacja klientów](https://docs.nextcloud.com/server/latest/admin_manual/maintenance/restore.html)
- [Immich: kopia i odtwarzanie](https://docs.immich.app/administration/backup-and-restore/)

Przykład dopasowano do plików Compose w repozytorium. Wymaga próbnego
wykonania na własnej maszynie testowej; nie jest deklaracją przetestowanego
odtwarzania całego serwera.
