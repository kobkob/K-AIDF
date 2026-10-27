FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Unprivileged runtime user; the app only needs to read its code and the
# read-only mounted K-AIDF repository.
RUN groupadd --system appgroup \
    && useradd --system --gid appgroup --home-dir /app --shell /usr/sbin/nologin appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py maturity.py ./

EXPOSE 7777

USER appuser

# Production WSGI server instead of the Flask development server.
CMD ["gunicorn", "--bind", "0.0.0.0:7777", "--workers", "2", "--access-logfile", "-", "app:app"]
