from flask import Flask
import redis
import os
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", 6379))

try:
    r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True, socket_connect_timeout=5)
    r.ping()  # Test connection at startup
    app.logger.info(f"Connected to Redis at {redis_host}:{redis_port}")
except redis.exceptions.ConnectionError as e:
    app.logger.warning(f"Redis unavailable at {redis_host}:{redis_port}: {e}")
    r = None

@app.route("/")
def index():
    if r is None:
        return "Redis unavailable — visitor counter disabled", 503
    try:
        count = r.incr("visitor_count")
        return f"This is the {count} visitor."
    except redis.exceptions.ConnectionError as e:
        app.logger.exception(f"Redis connection error: {e}")
        return "Redis unavailable — try again later", 503

@app.route("/health")
def health():
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
