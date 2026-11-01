# Dyski z danymi, RAID i kopie zapasowe

## Jak działa pamięć masowa w tym homelabie

Dyski przechowujące dane są w tym serwerze zorganizowane w macierz RAID, aby
ograniczyć przestój przy awarii dysku. To opis konfiguracji tego homelaba,
a nie wymaganie dla każdego, kto kopiuje starter. Nie podajemy poziomu RAID,
liczby dysków ani kontrolera — te parametry należy sprawdzić w konfiguracji
konkretnej maszyny, zamiast zgadywać je na podstawie nazwy katalogu
montowania lub systemu plików (np. ext4).

## Sprawdź istniejącą konfigurację

Poniższe polecenia służą do odczytu informacji. Dla programowego RAID Linux
opartego na `mdadm`:

```bash
lsblk -o NAME,SIZE,FSTYPE,TYPE,MOUNTPOINTS
cat /proc/mdstat
sudo mdadm --detail --scan
```

Jeśli wynik pokaże macierz `/dev/mdX`, sprawdź jej stan dokładnymi danymi:

```bash
sudo mdadm --detail /dev/mdX
```

Zastąp `/dev/mdX` urządzeniem z własnego wyniku. `mdadm` nie opisze
konfiguracji sprzętowego RAID ani każdej konfiguracji ZFS; użyj narzędzi
odpowiedniego kontrolera/systemu plików. Zanim zmienisz partycje lub
macierz, ustal dokładny układ dysków, sprawdź kopię i przygotuj procedurę
odzyskiwania. **Nie uruchamiaj `mdadm --create`, formatowania ani
partycjonowania na dyskach z danymi** — takie operacje mogą je zniszczyć.

## Dobór i utrzymanie RAID

RAID1 (lustro), RAID5, RAID6 i RAID10 różnią się minimalną liczbą dysków,
użyteczną pojemnością oraz odpornością na jednoczesne awarie. Dobór zależy
od liczby i pojemności dysków, obciążenia oraz akceptowanego czasu odbudowy.
Nie wybieraj poziomu tylko na podstawie maksymalnej pojemności.

Monitoruj stan macierzy i kondycję dysków (SMART), skonfiguruj powiadomienia,
reaguj na zdegradowanie macierzy i miej plan wymiany/odbudowy. Jeśli to
możliwe, zasilanie serwera i dysków zabezpiecz UPS-em. Po wymianie dysku
sprawdź zakończenie odbudowy oraz integralność danych.

## RAID to nie backup

RAID może pozwolić serwerowi działać po awarii określonej liczby dysków,
zależnie od poziomu RAID. Nie chroni przed przypadkowym skasowaniem,
nadpisaniem, ransomware, błędem aplikacji, kradzieżą, pożarem, awarią hosta
ani utratą całej macierzy. Błąd lub skasowanie pliku może natychmiast
zsynchronizować się na wszystkich dyskach.

Przechowuj kopię zapasową na innym urządzeniu lub poza lokalizacją serwera.
Uwzględnij pliki, bazy danych, konfigurację aplikacji i sekrety potrzebne
do odtworzenia. Ogranicz dostęp do kopii, rozważ kopię offline/niezmienną
i regularnie wykonuj próbne odtwarzanie. Więcej szczegółów o usługach:
[kopie i odtwarzanie Nextcloud/Immich](backup-and-restore.md).

### Źródła

- [mdadm — dokumentacja pakietu Ubuntu](https://manpages.ubuntu.com/manpages/noble/man8/mdadm.8.html)
- [Ubuntu Server: zarządzanie pamięcią masową](https://ubuntu.com/server/docs/how-to/storage/)
- [Ochrona przed ransomware — CISA](https://www.cisa.gov/stopransomware/ransomware-guide)
