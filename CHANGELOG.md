# Changelog

## Unreleased
- Dokumentacja: subdomeny usług i działanie nginx-proxy.
- Kreator obsługuje rodziny Debian, Fedora, RHEL (Rocky/Alma), Arch i openSUSE (wykrywanie przez `ID_LIKE`).
- Kreator wykrywa usługi z `containers/*/wizard.json`; nowy kontener nie wymaga zmian w kodzie.
- Nowa kolejność pytań: Docker i Cockpit, tryb sieci (IP/DDNS), lista usług.
- Kreator może zainstalować klienta DDNS na hoście (ddclient, inadyn).
- Dokument DDNS z wymaganiami routera, NAT, firewalla i CGNAT.
- Szablon Django jako alternatywa dla WordPressa.
- Updater instalowany przez kreator (SMTP, hasło zatwierdzania, timery systemd); kod w `containers/updater`.
- Usunięto główny compose i `stacks/` — źródłem są `containers/` i kreator.
- Dodano CI, Makefile, SECURITY i CONTRIBUTING.
- Dodano `.editorconfig`, `containers/django/.dockerignore` oraz reguły `.gitignore` dla `state/` i cache testów.
