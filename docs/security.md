# Bezpieczeństwo

- Domyślne porty są związane z `127.0.0.1`. Nie zmieniaj tego na `0.0.0.0`
  bez świadomego ograniczenia dostępu zaporą do zaufanej sieci.
- Nie wystawiaj Nextcloud ani Immich bezpośrednio do Internetu przez HTTP.
  Do dostępu z Internetu skonfiguruj TLS, reverse proxy, poprawne domeny
  zaufane i firewall. Rozważ VPN jako prostszą alternatywę.
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
