"""
Visitor counter routes.
"""

import logging
from flask import Blueprint, current_app, jsonify

log = logging.getLogger(__name__)

visitor_bp = Blueprint('visitor', __name__)


@visitor_bp.route('/', methods=['GET'])
def index():
    """Display visitor count."""
    from services.cache import get_cache_service
    
    cache = get_cache_service()
    
    if not cache or not cache.is_available():
        return jsonify({
            "error": "Visitor counter unavailable (Redis connection failed)",
            "status": "degraded"
        }), 503
    
    try:
        count = cache.increment("visitor_count", 1)
        if count is None:
            return jsonify({
                "error": "Failed to increment counter",
                "status": "error"
            }), 500
        
        return jsonify({
            "message": f"This is the {count} visitor.",
            "count": count,
            "status": "ok"
        }), 200
    
    except Exception as e:
        log.exception(f"Unexpected error in index route: {e}")
        return jsonify({
            "error": "Internal server error",
            "status": "error"
        }), 500
