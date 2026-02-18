"""
CDS Visitor Application.
Production-grade Flask app with Redis counter and comprehensive error handling.
"""

import logging
import sys
from flask import Flask

from config.settings import get_config
from services.cache import init_cache_service
from routes.visitor import visitor_bp
from routes.health import health_bp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
)
log = logging.getLogger(__name__)


def create_app():
    """Factory function to create and configure the Flask app."""
    app = Flask(__name__)
    
    # Load configuration
    config = get_config()
    app.config['JSON_SORT_KEYS'] = False
    
    # Initialize Redis cache service
    init_cache_service(
        host=config.redis.host,
        port=config.redis.port,
        db=config.redis.db,
        password=config.redis.password,
        socket_connect_timeout=config.redis.socket_connect_timeout,
        max_retries=config.max_retries,
    )
    
    # Register blueprints
    app.register_blueprint(visitor_bp)
    app.register_blueprint(health_bp)
    
    # Request logging middleware
    @app.before_request
    def log_request():
        from flask import request
        log.info(f"{request.method} {request.path} from {request.remote_addr}")
    
    @app.after_request
    def log_response(response):
        log.info(f"Response: {response.status_code}")
        return response
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return {"error": "Not found", "status": 404}, 404
    
    @app.errorhandler(500)
    def internal_error(error):
        log.exception("Internal server error")
        return {"error": "Internal server error", "status": 500}, 500
    
    log.info(f"App initialized in {config.environment} environment")
    return app


app = create_app()


if __name__ == "__main__":
    config = get_config()
    app.run(
        host=config.flask.host,
        port=config.flask.port,
        debug=config.flask.debug,
    )
