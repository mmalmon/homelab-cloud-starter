# Immich

Samodzielnie hostowana alternatywa dla Zdjęć Google: biblioteka zdjęć i wideo
z wyszukiwaniem, albumami i rozpoznawaniem twarzy.

## Synchronizacja zdjęć z telefonów

Oficjalna aplikacja mobilna Immich (Android i iOS) działa podobnie do aplikacji
Galeria/Zdjęcia Google: po zalogowaniu na Twój serwer wysyła zdjęcia i wideo
z wybranych albumów telefonu automatycznie w tle (opcja *Backup*).

1. Zainstaluj aplikację ze [Sklepu Google Play](https://play.google.com/store/apps/details?id=app.alextran.immich)
   lub [F-Droid/GitHub](https://github.com/immich-app/immich/releases).
2. Wpisz adres serwera (np. `https://zdjecia.example.com`) i zaloguj się.
3. Włącz kopię zapasową i wybierz albumy do synchronizacji.

Poza domem aplikacja potrzebuje dostępu do serwera przez HTTPS (domena z
`nginx-proxy`, publiczny IP lub DDNS) albo przez VPN. Synchronizacja jest
kopią zapasową zdjęć z telefonu; sama nie zastępuje kopii samego serwera.
Zobacz [dokumentację aplikacji](https://docs.immich.app/features/mobile-app/)
i [kopii zapasowej](https://docs.immich.app/administration/backup-and-restore/).
