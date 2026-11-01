# Django (alternatywa dla WordPressa)

Minimalny szablon do wdrożenia własnej strony lub aplikacji w Django z
PostgreSQL, Gunicorn i WhiteNoise. W przeciwieństwie do innych usług budowany
jest własny obraz (`Dockerfile`), a kod aplikacji leży w `app/`.

- Podmień `app/config/urls.py` i dodaj własne aplikacje w `app/`
  (zależności w `app/requirements.txt`), potem `docker compose build`.
- Kreator ustawia `DJANGO_HOST`; hosty `ALLOWED_HOSTS` i nagłówki proxy są
  już skonfigurowane. Zaufane źródła CSRF są
  tworzone jako `https://<host>`; inne dodaj w `DJANGO_CSRF_TRUSTED_ORIGINS`.
- Konto administratora: `docker compose exec django python manage.py createsuperuser`.
- `DEBUG` jest wyłączony. Dokumentacja wdrożeń:
  <https://docs.djangoproject.com/en/stable/howto/deployment/>.
