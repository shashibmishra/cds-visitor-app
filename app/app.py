from flask import Flask
import redis
import os

app = Flask(__name__)

redis_host = os.getenv("REDIS_HOST")
r = redis.Redis(host=redis_host, port=6379, decode_responses=True)

@app.route("/")
def index():
    count = r.incr("visitor_count")
    return f"This is the {count} visitor."

@app.route("/health")
def health():
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
