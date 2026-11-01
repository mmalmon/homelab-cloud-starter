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
Home Assistant (tryb host), MQTT, SMB i Minecraft nie są routingowane przez
HTTP reverse proxy. Panel Zigbee2MQTT jest administracyjny — nie wystawiaj go
publicznie bez skonfigurowanego uwierzytelniania.
