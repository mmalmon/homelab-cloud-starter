# Ubuntu Server, Docker i Cockpit

Ten poradnik opisuje bezpieczny punkt wyjścia dla nowego serwera homelab.
Nazwy interfejsów, podsieć LAN, adres serwera i wersję Ubuntu dopasuj do
własnej sieci. Nie wykonuj poleceń zmieniających partycje ani reguły sieciowe
bez sprawdzenia ich wpływu na istniejący system.

## 1. Instalacja Ubuntu Server

1. Pobierz obraz **Ubuntu Server LTS** z [oficjalnej strony Ubuntu](https://ubuntu.com/download/server)
   i przygotuj nośnik instalacyjny według [instrukcji instalacji](https://ubuntu.com/server/docs/how-to/installation/).
2. W instalatorze ustaw nazwę hosta, utwórz zwykłe konto administratora
   (bezpośrednia praca jako `root` nie jest potrzebna) i wybierz właściwy
   dysk/układ partycji. Instalacja może wymazać wybrany dysk — upewnij się,
   że wskazujesz właściwe urządzenie i masz kopię ważnych danych.
3. Zainstaluj OpenSSH Server, jeśli chcesz zarządzać hostem przez SSH.
   Zarezerwuj adres serwera w DHCP routera albo skonfiguruj stały adres
   zgodnie ze swoją siecią.
4. Po pierwszym logowaniu zainstaluj aktualizacje i podstawowe narzędzia:

   ```bash
   sudo apt update
   sudo apt full-upgrade
   sudo apt install ca-certificates curl ufw unattended-upgrades
   sudo reboot
   ```

Po restarcie sprawdź wersję Ubuntu przez `lsb_release -a` i sieć przez
`ip address`. Zanim włączysz zaporę, upewnij się, że masz dostęp do lokalnej
konsoli lub inną drogę odzyskania dostępu.

## 2. SSH i konto administratora

Jeśli administrujesz zdalnie, skonfiguruj klucz SSH z komputera klienckiego
i **sprawdź nowe połączenie w drugim terminalu**, zanim zmienisz ustawienia
serwera:

```bash
ssh-copy-id NAZWA_UZYTKOWNIKA@ADRES_SERWERA
ssh NAZWA_UZYTKOWNIKA@ADRES_SERWERA
```

Użyj prawdziwej nazwy konta i adresu hosta zamiast tekstów przykładowych.
Po potwierdzeniu logowania kluczem można wyłączyć zdalne logowanie hasłem
i logowanie roota, tworząc drop-in SSH i sprawdzając konfigurację przed
przeładowaniem:

```bash
sudo tee /etc/ssh/sshd_config.d/00-local-hardening.conf <<'EOF'
PasswordAuthentication no
PermitRootLogin no
EOF
sudo sshd -t
sudo systemctl reload ssh
```

Nie wyłączaj uwierzytelniania hasłem, dopóki nie potwierdzisz dostępu kluczem
i nie zachowasz działającej sesji administracyjnej. Zmiany SSH mogą odciąć
zdalny dostęp, jeśli klucz lub konfiguracja są błędne.

## 3. Firewall UFW

Najpierw dodaj wyjątki dla używanych usług, dopiero potem włącz UFW. Poniższa
wartość `192.0.2.0/24` jest zarezerwowana do przykładów i **nie jest Twoją
podsiecią LAN** — zastąp ją rzeczywistą podsiecią. Jeśli SSH używa innego
portu, zmień `22`.

```bash
LAN_CIDR="192.0.2.0/24"  # zastąp adresem swojej podsieci LAN
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from "$LAN_CIDR" to any port 22 proto tcp
sudo ufw allow from "$LAN_CIDR" to any port 9090 proto tcp
sudo ufw enable
sudo ufw status verbose
```

Reguła dla `9090/tcp` pozwala otworzyć Cockpit wyłącznie z podanej podsieci.
Nie dodawaj szerokiej reguły `allow 9090` ani nie wystawiaj Cockpit do
Internetu. Jeśli nie używasz SSH lub Cockpit, pomiń odpowiadającą im regułę.
Zanim aktywujesz UFW przez SSH, upewnij się, że reguła SSH pasuje do klienta,
inaczej możesz utracić dostęp.

### 3.1 UFW a opublikowane porty Dockera

Docker tworzy własne reguły sieciowe. Ruch do portów opublikowanych przez
Compose może zostać przekierowany **przed regułami UFW**, więc samo
`ufw deny` nie jest wystarczającą ochroną usług kontenerowych.

- Starter domyślnie wiąże porty aplikacji z `127.0.0.1`. Zachowaj to
  ustawienie, jeśli dostęp ma odbywać się lokalnie lub przez reverse proxy.
- Nie ustawiaj `BIND_ADDRESS=0.0.0.0` bez przemyślanej filtracji ruchu do
  sieci Docker i sprawdzenia dostępu z innego urządzenia.
- Nie wyłączaj reguł iptables Dockera, żeby „naprawić” UFW — może to zepsuć
  izolację i łączność kontenerów.
- Jeśli potrzebujesz portów dostępnych w LAN, zaprojektuj i przetestuj
  reguły w łańcuchu `DOCKER-USER` zgodnie z [dokumentacją firewalla Dockera](https://docs.docker.com/engine/network/packet-filtering-firewalls/).
  Użyj także reguł zapory routera i sprawdź osobno IPv4 oraz IPv6.
- Do dostępu z Internetu przekierowuj tylko świadomie wybrane porty HTTPS
  reverse proxy; nie przekierowuj portów baz danych, Cockpit, SSH ani
  surowych portów Nextcloud/Immich. VPN jest często prostszą opcją.

## 4. Cockpit

Cockpit udostępnia panel administracyjny hosta przez HTTPS na porcie `9090`.
Zaloguj się zwykłym kontem systemowym administratora, nie kontem `root`.

```bash
sudo apt update
sudo apt install cockpit
sudo systemctl enable --now cockpit.socket
systemctl status cockpit.socket
```

Z komputera w dozwolonej podsieci otwórz `https://ADRES_SERWERA:9090`.
Początkowy certyfikat może być samopodpisany; sprawdź, czy łączysz się
z właściwym hostem, i nie traktuj tego jako konfiguracji do wystawienia
panelu do Internetu. Cockpit ma szerokie uprawnienia administracyjne —
aktualizuj system, ogranicz dostęp sieciowy i używaj unikalnych haseł/kluczy.

## 5. Docker Engine i Compose

Poniższa metoda korzysta z oficjalnego repozytorium APT Dockera. Sprawdź
na [liście wspieranych wersji Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
czy Twoje wydanie i architektura są obsługiwane. Nie uruchamiaj wygodnego
skryptu instalacyjnego Dockera na serwerze produkcyjnym.

Dodaj klucz i repozytorium:

```bash
sudo apt update
sudo apt install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \\
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
```

Zainstaluj Engine, CLI, containerd, Buildx i Compose plugin:

```bash
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker run hello-world
sudo docker compose version
```

Do poleceń Docker można dodawać `sudo`. Alternatywnie konto można dodać do
grupy `docker`, ale **członkostwo w tej grupie daje uprawnienia równoważne
root** i może pozwolić ominąć ograniczenia konta administratora. Dodawaj
wyłącznie zaufane konta na jednoosobowym hoście:

```bash
sudo usermod -aG docker "$USER"
```

Wyloguj się i zaloguj ponownie, żeby zmiana zadziałała. Nie udostępniaj
demona Dockera przez niezabezpieczony TCP (`2375`) ani nie montuj jego
gniazda (`/var/run/docker.sock`) w niezaufanych kontenerach. Szczegóły
wpływu grupy `docker` opisuje [dokumentacja post-install Dockera](https://docs.docker.com/engine/install/linux-postinstall/).

## 6. Aktualizacje i kontrola

`unattended-upgrades` pomaga automatycznie instalować aktualizacje
bezpieczeństwa Ubuntu. Sprawdź aktywne timery, a większe aktualizacje
wykonuj i weryfikuj świadomie:

```bash
sudo systemctl status apt-daily-upgrade.timer
systemctl list-timers 'apt-daily*'
sudo apt update
sudo apt upgrade
```

Po aktualizacji jądra zaplanuj restart i sprawdź, czy Docker, Cockpit
i kontenery wróciły:

```bash
sudo systemctl status docker cockpit.socket
sudo ufw status verbose
sudo docker compose ps
```

## 7. Dyski z danymi i RAID

W opisywanym homelabie dyski przechowujące dane są połączone w macierz RAID,
żeby ograniczyć przestój i utratę dostępności w razie awarii dysku. To opis
układu tego serwera, a nie wymaganie dla każdego czytelnika. Sam punkt
montowania lub system plików (na przykład ext4) nie mówi, czy pod spodem jest
RAID ani jaki to poziom.

Dokładny poziom macierzy, urządzenia i odporność na awarie trzeba sprawdzić
na danym hoście przed planowaniem zmian:

```bash
lsblk -o NAME,SIZE,FSTYPE,TYPE,MOUNTPOINTS
cat /proc/mdstat
sudo mdadm --detail --scan
```

`mdadm` dotyczy programowego RAID Linux; sprzętowy RAID lub rozwiązania ZFS
sprawdza się innymi narzędziami. Jeśli `mdadm --detail --scan` zwróci
urządzenie, szczegóły konkretnej macierzy można odczytać poleceniem
`sudo mdadm --detail /dev/mdX`, zastępując `/dev/mdX` nazwą z wyniku.
Nie uruchamiaj poleceń `mdadm --create`, formatowania ani partycjonowania
na dyskach z danymi: błędne polecenie może zniszczyć macierz i pliki.

RAID1 lustrzany, RAID5, RAID6 i RAID10 mają różną pojemność i odporność na
awarie; nie ma jednego poziomu właściwego dla każdego zestawu dysków. Przy
wyborze uwzględnij liczbę i rozmiar dysków, czas odbudowy, obciążenie oraz
scenariusz jednoczesnych awarii. Monitoruj stan macierzy i SMART, reaguj na
błędy, utrzymuj aktualny plan wymiany dysku, a jeśli to możliwe użyj UPS.

**RAID nie zastępuje kopii zapasowej.** Nie chroni przed przypadkowym
skasowaniem lub nadpisaniem, ransomware, kradzieżą, pożarem, awarią hosta ani
uszkodzeniem całej macierzy. Kopię ważnych danych trzymaj na niezależnym
nośniku lub poza lokalizacją serwera i regularnie testuj odtwarzanie.

Przed wdrożeniem usług z tego repozytorium przejdź do [szybkiego startu](../README.md#szybki-start-nextcloud)
i przeczytaj [zasady bezpieczeństwa](security.md).

## Źródła

- [Instalacja Ubuntu Server](https://ubuntu.com/server/docs/how-to/installation/)
- [Ubuntu Server: firewall UFW](https://ubuntu.com/server/docs/how-to/security/firewalls/)
- [Instalacja Docker Engine na Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
- [Docker: filtrowanie pakietów i firewalle](https://docs.docker.com/engine/network/packet-filtering-firewalls/)
- [Docker: kroki po instalacji](https://docs.docker.com/engine/install/linux-postinstall/)
- [Cockpit: instalacja i konfiguracja](https://cockpit-project.org/running.html)
- [mdadm — dokumentacja pakietu Ubuntu](https://manpages.ubuntu.com/manpages/noble/man8/mdadm.8.html)
