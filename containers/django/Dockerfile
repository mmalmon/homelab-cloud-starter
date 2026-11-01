FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --system --uid 10001 django

COPY app/ .
COPY entrypoint.sh /entrypoint.sh
RUN chmod 0755 /entrypoint.sh && chmod -R a+rX /app && mkdir -p /app/staticfiles /app/media \
    && chown -R django /app/staticfiles /app/media

USER django
ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
