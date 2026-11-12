"""A small background worker. It processes fake jobs forever.

Your task (see the lab): expose Prometheus metrics from this program on port 8001.
Run it in the background with:   python3 /lab/apps/worker.py >/tmp/worker.log 2>&1 &
"""
import random
import time


def process(job_id):
    # pretend to do some work
    time.sleep(random.uniform(0.05, 0.4))
    return random.random() > 0.1   # True = success


def main():
    job_id = 0
    while True:
        job_id += 1
        ok = process(job_id)
        print(f"job {job_id}: {'ok' if ok else 'failed'}", flush=True)


if __name__ == "__main__":
    main()
