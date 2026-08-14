from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager

import time

db = SQLAlchemy()
jwt = JWTManager()

login_attempts = {}

def is_rate_limited(ip):
    """Simple bounded in-memory rate limiter for login. Max 5 attempts per 60s."""
    global login_attempts
    # Bound the dictionary to prevent memory leak DoS
    if len(login_attempts) > 1000:
        login_attempts.clear()

    now = time.time()

    # Initialize or clean up old attempts
    if ip not in login_attempts:
        login_attempts[ip] = []

    # Remove attempts older than 60 seconds
    login_attempts[ip] = [t for t in login_attempts[ip] if now - t < 60]

    if len(login_attempts[ip]) >= 5:
        return True

    login_attempts[ip].append(now)
    return False
