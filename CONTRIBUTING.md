# Współpraca

1. Każda usługa to `containers/<nazwa>/` z `compose.yaml`, `.env.example` i README.
2. Nie commituj sekretów ani plików `.env`.
3. Przed PR uruchom `make check` (lint, testy, walidacja Compose).
4. Zmiany w kreatorze (`wizard/`) wymagają testów w `tests/`.
5. Aktualizuj dokumentację w `docs/` i `CHANGELOG.md`.
