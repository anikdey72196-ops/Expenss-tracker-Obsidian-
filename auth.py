from imports import (
    Blueprint, request, jsonify,
    generate_password_hash, check_password_hash,
    create_access_token, User, db
)


import time
api_login_attempts = {}
API_LOGIN_RATE_LIMIT_SECONDS = 60
API_LOGIN_MAX_ATTEMPTS = 5

def check_api_login_rate_limit(ip_address):
    now = time.time()
    # Cleanup old IPs to prevent memory leak (DoS)
    keys_to_delete = [ip for ip, atts in api_login_attempts.items() if not any(now - t < API_LOGIN_RATE_LIMIT_SECONDS for t in atts)]
    for key in keys_to_delete:
        del api_login_attempts[key]

    attempts = api_login_attempts.get(ip_address, [])
    attempts = [t for t in attempts if now - t < API_LOGIN_RATE_LIMIT_SECONDS]

    if len(attempts) >= API_LOGIN_MAX_ATTEMPTS:
        api_login_attempts[ip_address] = attempts
        return False

    attempts.append(now)
    api_login_attempts[ip_address] = attempts
    return True

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

@auth_bp.route('/login', methods=['POST'])
def login():
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    if not check_api_login_rate_limit(client_ip):
        return jsonify({"error": "Too many login attempts. Please try again later."}), 429

    """Authenticate and generate JWT."""
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
