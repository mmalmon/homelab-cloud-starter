# DDNS — stały adres nazwy przy zmiennym IP

Gdy dostawca internetu zmienia Twój publiczny adres IP, usługa DDNS utrzymuje
aktualną nazwę (np. `moj-dom.duckdns.org` lub rekord w Twojej domenie), a
`nginx-proxy` kieruje ruch tej nazwy do właściwych kontenerów. Przy stałym
publicznym IPv4 DDNS nie jest potrzebny — wystarczy zwykły rekord `A`.

DDNS w tym projekcie **nie działa w Dockerze**. Aktualizację adresu wykonuje
jedno z poniższych:

| Wariant | Gdzie działa | Uwagi |
|---|---|---|
| Klient DDNS wbudowany w router | router | Najprostszy; część dostawców DDNS **wymaga** konfiguracji po stronie routera. |
| `ddclient` lub `inadyn` (kreator może zainstalować) | host (pakiet systemowy, usługa `systemd`) | Wspierani dostawcy: DuckDNS, Cloudflare, No-IP. |
| Inny klient/skrypt dostawcy | host lub router | Konfigurujesz samodzielnie wg dokumentacji dostawcy. |

## Klient DDNS instalowany przez kreator

W trybie „DDNS” kreator na końcu pyta, czy zainstalować klienta (`ddclient`
lub `inadyn`) albo pominąć ten krok. Dla wybranego dostawcy prosi o dane
logowania (token wpisywany bez echa), instaluje pakiet systemowy, zapisuje
konfigurację z uprawnieniami `600` (`/etc/ddclient.conf` (Debian, openSUSE, RHEL),
`/etc/ddclient/ddclient.conf` na Fedorze i Archu lub `/etc/inadyn.conf`) i włącza
usługę. Aktualizowane są hostnames wybranych usług webowych.

- **DuckDNS:** każdy hostname musi mieć postać `nazwa.duckdns.org` (bez
  sub-subdomen); token pochodzi z konta DuckDNS.
- **Cloudflare:** podaj strefę (domenę bazową) i token API z uprawnieniami
  `Zone:DNS:Edit` oraz `Zone:Zone:Read` — nie używaj globalnego klucza.
- **No-IP:** login i hasło/klucz DDNS (nie hasło konta, jeśli dostawca oferuje
  osobne dane dla klienta).

`ddclient` instaluje się na Debianie/Ubuntu, Fedorze, RHEL (z EPEL), Archu i
openSUSE; `inadyn` tylko na Debianie/Ubuntu i Fedorze (brak pakietu w Arch i
openSUSE). Na innych systemach skonfiguruj klienta ręcznie.

Kreator nie weryfikuje konta ani poprawności nazw u dostawcy. Sprawdź logi:
`journalctl -u ddclient` lub `journalctl -u inadyn`.

## Sama instalacja klienta to nie wszystko

Klient DDNS tylko aktualizuje rekord DNS. Aby usługi były osiągalne z
Internetu, nadal może być potrzebna konfiguracja:

- **router:** przekierowanie TCP `80` i `443` na LAN-owy adres serwera (stały
  adres lub rezerwacja DHCP); część dostawców DDNS wymaga też własnych
  ustawień klienta DDNS w routerze;
- **NAT i firewall:** reguły NAT/hairpin (dostęp do własnej domeny z LAN),
  zapora routera i hosta (UFW/firewalld) zezwalająca tylko na potrzebne porty;
- **CGNAT:** jeśli router nie ma publicznego adresu WAN, przekierowanie
  portów nie zadziała — poproś ISP o publiczny IPv4, użyj IPv6 albo VPN/tunelu;
- **IPv6:** rekord `AAAA` wymaga reguł zapory IPv6, a nie tylko NAT;
- **TLS:** certyfikat Let's Encrypt (HTTP-01) wymaga osiągalnego portu 80.

Zawsze sprawdź dostęp spoza własnej sieci (np. przez sieć komórkową).

## Źródła

[ddclient](https://github.com/ddclient/ddclient) ·
[inadyn](https://github.com/troglobit/inadyn) ·
[DuckDNS](https://www.duckdns.org/) ·
[Cloudflare — dynamiczne IP](https://developers.cloudflare.com/dns/manage-dns-records/how-to/managing-dynamic-ip-addresses/) ·
[No-IP — czym jest DDNS](https://www.noip.com/support/knowledgebase/what-is-dynamic-dns)
