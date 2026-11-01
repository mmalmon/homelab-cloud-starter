# nginx-proxy: domeny do kontenerów

`nginx-proxy` działa jako reverse proxy w kontenerze. DNS kieruje nazwę
domenową na adres serwera; reverse proxy odbiera żądanie i na podstawie
domeny/subdomeny z nagłówka `Host` przekazuje je do właściwego kontenera
aplikacji. To dwa osobne kroki — `nginx-proxy` nie jest serwerem DNS.

```text
cloud.example.net
       │ DNS: nazwa → adres serwera
       ▼
serwer:80/443 → kontener nginx-proxy
                    │ Host: cloud.example.net
                    ▼
              kontener Nextcloud
```

W typowej konfiguracji z projektem
[`nginx-proxy`](https://github.com/nginx-proxy/nginx-proxy) wygląda to tak:

1. Rekord DNS `A` (i w razie potrzeby `AAAA`) wskazuje na publiczny adres
   serwera. Dla dostępu tylko z LAN można użyć lokalnego DNS.
2. Router i firewall dopuszczają wybrane porty HTTP/HTTPS do hosta. Zwykle
   porty `80` i `443` są publikowane przez kontener proxy; nie publikuj
   bezpośrednio portów aplikacji, baz danych ani paneli administracyjnych.
3. Kontener `nginx-proxy` i kontenery usług webowych są dołączone do wspólnej
   sieci Docker. Usługa podaje obsługiwaną nazwę, zwykle przez zmienną
   `VIRTUAL_HOST=cloud.example.net`, oraz — jeśli to potrzebne — swój
   wewnętrzny port przez `VIRTUAL_PORT`.
4. `docker-gen` obserwuje metadane kontenerów, generuje konfigurację Nginx
   i przeładowuje ją, gdy usługi się pojawiają lub znikają. Żądanie trafia
   więc do usługi przypisanej do pasującej domeny.

Nie musisz wystawiać portu każdej aplikacji na hosta, jeśli proxy może
połączyć się z nią w sieci Docker. Szczegóły konfiguracji, sieci, zmiennych
i wymagań obrazu sprawdź w [oficjalnym README nginx-proxy](https://github.com/nginx-proxy/nginx-proxy#usage).

## HTTPS i certyfikaty

`nginx-proxy` sam w sobie nie oznacza, że certyfikat jest już wydany
i odnawiany. Można dobrać do niego osobny mechanizm ACME, np.
[`acme-companion`](https://github.com/nginx-proxy/acme-companion), albo
utrzymywać certyfikaty osobno przez [Certbot](https://certbot.eff.org/).
Wybierz jeden sposób zarządzania certyfikatami i sprawdź jego aktualną
dokumentację. Walidacja HTTP-01 wymaga osiągalności portu 80.

Przed wystawieniem usługi sprawdź poprawną domenę/trusted domains w samej
aplikacji i jej ustawienia reverse proxy. TLS na proxy nie zastępuje
uwierzytelniania aplikacji ani aktualizacji.

## Ograniczenia bezpieczeństwa

- Wystawiaj przez proxy tylko potrzebne usługi webowe. Nie kieruj w ten
  sposób publicznie do Cockpit, baz danych, MQTT, SMB ani paneli
  administracyjnych bez odrębnego, świadomego projektu dostępu.
- Dostęp do socketu/API Dockera używany do wykrywania kontenerów jest
  wrażliwym uprawnieniem. Ogranicz go do zaufanych komponentów i nie montuj
  socketu Docker w niezaufanych kontenerach.
- Porty Dockera mogą omijać reguły UFW. Zachowaj świadome mapowanie portów
  i sprawdź faktyczną osiągalność z LAN oraz z Internetu.
- DNS, przekierowanie portów routera, firewall hosta i routing do kontenera
  to osobne elementy — zweryfikuj każdy z nich.
