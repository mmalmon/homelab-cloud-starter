# Mapa homelaba

Ten przykład wyodrębnia podstawowe usługi chmurowe z większego homelaba:

| Rola | Przykład w tym repozytorium |
|---|---|
| Pliki i współpraca | Nextcloud + PostgreSQL + Redis |
| Zdjęcia i wideo | opcjonalny Immich + własna baza + Valkey |
| Reverse proxy i TLS | do skonfigurowania osobno pod domenę i zaporę |
| Biblioteka filmów i muzyki | Jellyfin jako osobny, opcjonalny stos |
| Automatyka domowa | Home Assistant, Zigbee2MQTT i MQTT — zależne od sprzętu |
| Własne aplikacje | osobne projekty, każda z własnym plikiem Compose |

W tej przykładowej konfiguracji każda aplikacja ma własną bazę tam, gdzie jest
to wymagane. Nie udostępnia się baz, portów administracyjnych ani wolumenów
między usługami bez potrzeby. Pliki Compose z innego serwera nie są
uniwersalnym szablonem: zwykle zawierają jego sieci, ścieżki hosta, domeny,
adresy, identyfikatory użytkowników i sekrety.

KADR i Planszownia są odrębnymi projektami i nie są kopiowane ani uruchamiane
przez ten starter. Przy własnych aplikacjach dodaj wyłącznie ich ogólną
konfigurację; repozytoria aplikacji i dane produkcyjne trzymaj osobno.

Przed dodaniem kolejnego stosu:

1. Zapisz wymagane porty, sieci i zależności.
2. Ustal oddzielne trwałe katalogi danych i kopię zapasową.
3. Przypnij oraz przetestuj wersje obrazów.
4. Wystaw usługę wyłącznie przez wybrany, zabezpieczony punkt wejścia.
