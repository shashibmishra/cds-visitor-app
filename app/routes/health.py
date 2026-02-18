"""
Health check routes.
"""

import logging
from flask import Blueprint, jsonify

log = logging.getLogger(__name__)

health_bp = Blueprint('health', __name__)


@health_bp.route('/health', methods=['GET'])
def health():
    """
    Health check endpoint.
    Returns 200 if app is running (Redis optional).
    """
    from services.cache import get_cache_service
    
    cache = get_cache_service()
    redis_healthy = cache and cache.is_available()
    
    return jsonify({
        "status": "ok",
        "app": "running",
        "redis": "ok" if redis_healthy else "unavailable"
    }), 200


@health_bp.route('/ready', methods=['GET'])
def readiness():
    """
    Readiness probe endpoint.
    Returns 200 only if both app AND Redis are healthy.
    Used by Kubernetes for pod readiness.
    """
    from services.cache import get_cache_service
    
    cache = get_cache_service()
    if not cache or not cache.is_available():
        return jsonify({
            "status": "not_ready",
            "reason": "Redis unavailable"
        }), 503
    
    return jsonify({
        "status": "ready"
    }), 200
