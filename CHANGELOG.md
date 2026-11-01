# Changelog

## Unreleased
- Kreator może zainstalować klienta DDNS na hoście (ddclient, inadyn).
- Dokument DDNS z wymaganiami routera, NAT, firewalla i CGNAT.
- Szablon Django jako alternatywa dla WordPressa.
- Updater instalowany przez kreator (SMTP, hasło zatwierdzania, timery systemd); kod w `containers/updater`.
- Usunięto główny compose i `stacks/` — źródłem są `containers/` i kreator.
- Dodano CI, Makefile, SECURITY i CONTRIBUTING.
- Dodano `.editorconfig`, `containers/django/.dockerignore` oraz reguły `.gitignore` dla `state/` i cache testów.
