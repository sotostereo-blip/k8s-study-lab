"""A fake web shop that creates its own traffic and exposes Prometheus metrics on :8000.

Metrics: http_requests_total, http_request_duration_seconds (histogram), shop_orders_in_queue,
shop_last_order_timestamp_seconds, app_info (with a noisy build_id label).
APP_NAME changes the version label only; the job label comes from the Prometheus config.
"""
import os
import random
import threading
import time

from prometheus_client import Counter, Gauge, Histogram, start_http_server

APP = os.getenv("APP_NAME", "shop")
REQUESTS = Counter("http_requests_total", "HTTP requests handled.", ["method", "path", "status"])
LATENCY = Histogram("http_request_duration_seconds", "Time spent handling an HTTP request.", ["path"])
QUEUE = Gauge("shop_orders_in_queue", "Orders waiting to be processed.")
LAST_ORDER = Gauge("shop_last_order_timestamp_seconds", "Unix time of the last order.")
INFO = Gauge("app_info", "Version information about the app.", ["app", "version", "build_id"])

# path: (requests per tick, share of 5xx errors, typical latency in seconds)
PATHS = {
    "/products": (9, 0.0, 0.04),
    "/": (6, 0.0, 0.02),
    "/cart": (4, 0.01, 0.08),
    "/checkout": (2, 0.25, 0.35),
    "/search": (1, 0.0, 0.6),
}


def traffic():
    rnd = random.Random(APP)
    queue = 10
    while True:
        for path, (n, err, lat) in PATHS.items():
            for _ in range(rnd.randint(max(1, n - 1), n + 1)):
                method = "POST" if path in ("/cart", "/checkout") and rnd.random() < 0.6 else "GET"
                status = "500" if rnd.random() < err else ("404" if rnd.random() < 0.02 else "200")
                REQUESTS.labels(method, path, status).inc()
                LATENCY.labels(path).observe(rnd.expovariate(1 / lat))
        queue = min(40, max(0, queue + rnd.randint(-3, 3)))
        QUEUE.set(queue)
        if rnd.random() < 0.3:
            LAST_ORDER.set(time.time())
        time.sleep(1)


if __name__ == "__main__":
    INFO.labels(APP, "1.4.2", f"{random.getrandbits(32):08x}").set(1)
    LAST_ORDER.set(time.time())
    threading.Thread(target=traffic, daemon=True).start()
    start_http_server(8000)
    print(f"{APP}: metrics on :8000/metrics")
    while True:
        time.sleep(3600)
