# Kontenery i stosy

Każda aplikacja ma osobny katalog z `compose.yaml` i `.env.example`.
Kreator zapisuje lokalne sekrety do `.env`, którego Git ignoruje. Dane
trwałe są domyślnie przechowywane w podkatalogu `data/`.
Dla Mosquitto kreator tworzy również plik hasła i ustawia jego właściciela na
UID/GID usługi, aby broker mógł go odczytać.

Większość usług korzysta z oficjalnych lub utrzymywanych upstreamowych
obrazów Docker, dlatego nie potrzebuje własnego Dockerfile. Dodaj Dockerfile
wyłącznie wtedy, gdy dany serwis wymaga zbudowania własnego obrazu; unikaj
kopiowania bazowego Dockerfile upstream bez potrzeby.

Stosy z interfejsem HTTP deklarują `VIRTUAL_HOST` i dołączają do wspólnej
sieci `homelab-proxy`. Kreator przypisuje domenę i dodaje tylko wybrane usługi.
Django i WordPress są alternatywami: Django buduje własny obraz z `app/`.
Home Assistant (tryb host), MQTT, SMB, Minecraft i F.E.A.R. Combat nie są routingowane przez
HTTP reverse proxy. Panel Zigbee2MQTT jest administracyjny — nie wystawiaj go
publicznie bez skonfigurowanego uwierzytelniania.

## Dodawanie własnego kontenera

Kreator wykrywa usługi automatycznie: wystarczy katalog
`containers/<nazwa>/` (małe litery, cyfry i `-`) z plikami `compose.yaml`,
`.env.example` i `wizard.json`. Katalog bez `wizard.json` lub z błędnym
manifestem jest pomijany z ostrzeżeniem, a testy w CI to wykryją.

```json
{
  "title": "Gitea",
  "order": 65,
  "requires": ["nextcloud"],
  "web": {"host_env": "GITEA_HOST", "tls_env": "GITEA_TLS_HOST", "public": true}
}
```

- `title` — nazwa na liście kreatora (wymagane).
- `order` — kolejność na liście i przy uruchamianiu (domyślnie 1000).
- `requires` — usługi, które kreator doda razem z tą (opcjonalnie).
- `web` — dla usług HTTP: nazwy zmiennych hostname i hostname TLS z
  `compose.yaml` (`VIRTUAL_HOST`/`LETSENCRYPT_HOST`); kreator zapyta o domenę,
  skonfiguruje `nginx-proxy` i Let's Encrypt. `public: false` oznacza panel
  tylko LAN, bez certyfikatu publicznego.
- `hidden` — usługa wewnętrzna, niewidoczna na liście (tak jest `nginx-proxy`).

Kreator sam wypełni tylko wartości sieciowe. Dodatkowe pytania (SMTP, ścieżki
mediów) wymagają kodu w `wizard/`; pozostałe zmienne uzupełnij w `.env`.

## F.E.A.R. Combat

[Stos fear-combat](fear-combat/README.md) buduje lokalny obraz i wymaga
własnych plików Linux Dedicated Server/SEC2. Kreator sprawdza ich obecność,
ustawia adres, port UDP i UID/GID; nie pobiera binariów i nie nadpisuje
lokalnego ServerOptions.txt. Usługa nie potrzebuje reverse proxy.
