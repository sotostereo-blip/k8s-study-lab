# Small demo services for the Prometheus lab:
#   shop.py    - a fake web app that serves Prometheus metrics on :8000 (prometheus_client)
#   webhook.py - an Alertmanager webhook receiver on :9000 that keeps every notification
FROM python:3.13-alpine3.22
RUN pip install --no-cache-dir prometheus_client==0.25.0
COPY shop.py webhook.py /app/
ENV PYTHONUNBUFFERED=1
WORKDIR /app
CMD ["python", "/app/shop.py"]
