from imports import (
    Blueprint, request, jsonify,
    generate_password_hash, check_password_hash,
    create_access_token, User, db
)
import time


auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"error": "Username and password are required"}), 400

    if not isinstance(data['username'], str) or len(data['username']) > 80:
        return jsonify({"error": "Username must be a string not exceeding 80 characters"}), 400

    if not isinstance(data['password'], str) or len(data['password']) > 72:
        return jsonify({"error": "Password must be a string not exceeding 72 characters"}), 400

    username = data.get('username', '')
    password = data.get('password', '')

    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters."}), 400

    if not isinstance(data['password'], str) or len(data['password']) > 72:
        return jsonify({"error": "Password must be a string not exceeding 72 characters"}), 400

    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400
    username = data.get('username', '')
    password = data.get('password', '')

    if not isinstance(username, str) or len(username) < 3 or len(username) > 80:
        return jsonify({"error": "Username must be between 3 and 80 characters."}), 400

    if len(password) < 8 or len(password) > 72:
        return jsonify({"error": "Password must be between 8 and 72 characters."}), 400
    
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 400
        
    hashed_password = generate_password_hash(password)
    new_user = User(username=username, password_hash=hashed_password)
    
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({"message": "User created successfully"}), 201


# In-memory dictionary for bounded rate limiting
_api_login_rate_limit_cache = {}

def _check_api_login_rate_limit(ip_address):
    """
    Bounded rate limiter: max 5 attempts per 5 minutes.
    Clears cache if it grows too large to prevent DoS via memory leak.
    """
    MAX_ATTEMPTS = 5
    WINDOW_SECONDS = 300
    MAX_CACHE_SIZE = 1000

    now = time.time()

    # Prune cache to prevent memory leak DoS
    if len(_api_login_rate_limit_cache) > MAX_CACHE_SIZE:
        # Remove expired entries
        expired_keys = [k for k, v in _api_login_rate_limit_cache.items() if now - v['start_time'] > WINDOW_SECONDS]
        for k in expired_keys:
            del _api_login_rate_limit_cache[k]

        # If still too large after pruning, clear it aggressively
        if len(_api_login_rate_limit_cache) > MAX_CACHE_SIZE:
            _api_login_rate_limit_cache.clear()

    record = _api_login_rate_limit_cache.get(ip_address)
    if not record or now - record['start_time'] > WINDOW_SECONDS:
        _api_login_rate_limit_cache[ip_address] = {'count': 1, 'start_time': now}
        return False

    if record['count'] >= MAX_ATTEMPTS:
        return True

    record['count'] += 1
    return False

@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate and generate JWT."""
    ip_address = request.remote_addr or 'unknown'
    if _check_api_login_rate_limit(ip_address):
        return jsonify({"error": "Too many login attempts. Please try again later."}), 429

    data = request.get_json()

    
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"error": "Username and password are required"}), 400
        
    if not isinstance(data['username'], str) or not isinstance(data['password'], str) or len(data['username']) > 80 or len(data['password']) > 128:
        return jsonify({"error": "Invalid username or password"}), 401

    user = User.query.filter_by(username=data['username']).first()
    
    if not user or not check_password_hash(user.password_hash, data['password']):
        return jsonify({"error": "Invalid username or password"}), 401
        
    # Generate token using user ID
    access_token = create_access_token(identity=str(user.id))
    return jsonify(access_token=access_token), 200
