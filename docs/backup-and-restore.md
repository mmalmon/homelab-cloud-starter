# Kopia zapasowa i odtwarzanie

Kopia powinna obejmować bazę danych **i** pliki aplikacji. Samo kopiowanie
lub synchronizowanie na ten sam dysk nie stanowi kopii zapasowej; trzymaj co
najmniej jedną kopię na innym nośniku lub w innej lokalizacji. Regularnie
sprawdzaj, czy da się ją odtworzyć.

## Nextcloud

1. Włącz tryb konserwacji:

   ```bash
   docker compose exec -u www-data nextcloud php occ maintenance:mode --on
   ```

2. Przy domyślnym `APPDATA_ROOT=./data` zapisz zrzut PostgreSQL i katalog
   aplikacji poza `data/`:

   ```bash
   mkdir -p backups
   docker compose exec -T nextcloud-db \
     sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
     > "backups/nextcloud-$(date +%F).sql"
   tar -C data -czf "backups/nextcloud-files-$(date +%F).tar.gz" nextcloud
   ```

3. Wyłącz tryb konserwacji i zweryfikuj, że pliki kopii nie są puste:

   ```bash
   docker compose exec -u www-data nextcloud php occ maintenance:mode --off
   test -s "backups/nextcloud-$(date +%F).sql"
   test -s "backups/nextcloud-files-$(date +%F).tar.gz"
   ```

Jeśli polecenie zatrzyma się przed wyłączeniem trybu konserwacji, wykonaj
polecenie `maintenance:mode --off` po sprawdzeniu stanu usługi.

## Immich (opcjonalnie)

Wykonaj kopię bazy oraz całej lokalizacji `IMMICH_UPLOAD_LOCATION`. Zapoznaj się
z aktualnym [poradnikiem kopii Immich](https://docs.immich.app/administration/backup-and-restore/);
nie zakładaj, że kopia samej biblioteki zawiera bazę i wszystkie ustawienia.

## Odtwarzanie

Odtwarzaj na zatrzymanych usługach i zgodnie z procedurą właściwej wersji
Nextcloud/Immich. Najpierw przetestuj procedurę na osobnym środowisku. Nie
nadpisuj działającego katalogu danych bez sprawdzonej kopii i planu powrotu.
