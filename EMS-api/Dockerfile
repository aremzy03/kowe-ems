# CapRover-compatible image. Local compose overrides the command to runserver.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production

WORKDIR /app

# libpq: Postgres client. WeasyPrint (report cards) needs Pango + friends —
# package list from https://doc.courtbouillon.org/weasyprint/stable/first_steps.html
# (Debian ≥ 11 / python:*-slim). fonts-dejavu-core avoids blank-glyph PDFs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz-subset0 \
        libgdk-pixbuf-2.0-0 \
        libffi8 \
        shared-mime-info \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# collectstatic is optional here (needs env/SECRET_KEY). Run at deploy if serving static from the app.
EXPOSE 80

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:80", "--workers", "2"]
