# Bezpieczeństwo

- Domyślne porty są związane z `127.0.0.1`. Nie zmieniaj tego na `0.0.0.0`
  bez świadomego ograniczenia dostępu zaporą do zaufanej sieci.
- Porty opublikowane przez Dockera mogą omijać reguły UFW. Nie traktuj
  `ufw deny` jako ochrony portów kontenerów; zachowaj domyślne wiązanie do
  localhost lub świadomie skonfiguruj filtrację sieci Docker. Zobacz
  [poradnik Ubuntu, Docker i Cockpit](ubuntu-docker-cockpit.md).
- Nie wystawiaj Nextcloud ani Immich bezpośrednio do Internetu przez HTTP.
  Do dostępu z Internetu skonfiguruj TLS, reverse proxy, poprawne domeny
  zaufane i firewall. Rozważ VPN jako prostszą alternatywę.
- Nie wystawiaj Cockpit (`9090`), SSH ani portów baz danych do Internetu.
  Ogranicz panel administracyjny do zaufanej sieci lub VPN.
- Konto w grupie `docker` ma uprawnienia równoważne root. Nie dodawaj do niej
  użytkowników ani procesów, którym nie ufasz.
- Nie udostępniaj demona Docker na niezabezpieczonym TCP ani nie montuj
  `/var/run/docker.sock` w niezaufanych kontenerach.
- `.env` zawiera sekrety. Nie wysyłaj go do Git, zgłoszeń, czatu ani logów.
  Użyj różnych haseł dla administratora Nextcloud i każdej bazy.
- Nie publikuj katalogu `data`, zrzutów baz ani kopii zapasowych.
- Ogranicz dostęp do panelu administratora, aktualizuj obrazy i sprawdzaj
  kopię zapasową przez próbne odtworzenie.
- Zmiana `NEXTCLOUD_TRUSTED_DOMAINS` po pierwszej inicjalizacji może nie
  zaktualizować ustawień aplikacji. Zmieniaj je zgodnie z dokumentacją obrazu.
- Przed aktualizacją Immich sprawdź plik Compose bieżącego wydania w jego
  oficjalnej dokumentacji.

Ten szablon nie zastępuje przeglądu bezpieczeństwa ani kopii zapasowej.
