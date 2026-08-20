import re

with open("auth.py", "r") as f:
    content = f.read()

header_add = """from extensions import db, jwt
import time

login_attempts = {}

def get_client_ip():
    if request.headers.getlist("X-Forwarded-For"):
        return request.headers.getlist("X-Forwarded-For")[0].split(',')[0].strip()
    return request.remote_addr

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')"""

content = content.replace("auth_bp = Blueprint('auth', __name__, url_prefix='/auth')", header_add)

login_add = """def login():
    \"\"\"Authenticate and generate JWT.\"\"\"

    ip = get_client_ip()
    current_time = time.time()

    # Prune old attempts and limit dict size to prevent memory leak
    if len(login_attempts) > 1000:
        login_attempts.clear()

    attempts = login_attempts.get(ip, [])
    attempts = [t for t in attempts if current_time - t < 300] # 5 minute window

    if len(attempts) >= 5:
        return jsonify({"error": "Too many login attempts. Please try again later."}), 429

    login_attempts[ip] = attempts
    """

content = content.replace('def login():\n    """Authenticate and generate JWT."""', login_add)

# Add failed attempt append for invalid username or password
invalid_cred_replace = """if not isinstance(data['username'], str) or not isinstance(data['password'], str) or len(data['username']) > 80 or len(data['password']) > 128:
        login_attempts[ip].append(current_time)
        return jsonify({"error": "Invalid username or password"}), 401

    user = User.query.filter_by(username=data['username']).first()

    if not user or not check_password_hash(user.password_hash, data['password']):
        login_attempts[ip].append(current_time)
        return jsonify({"error": "Invalid username or password"}), 401"""

content = content.replace("""if not isinstance(data['username'], str) or not isinstance(data['password'], str) or len(data['username']) > 80 or len(data['password']) > 128:
        return jsonify({"error": "Invalid username or password"}), 401

    user = User.query.filter_by(username=data['username']).first()

    if not user or not check_password_hash(user.password_hash, data['password']):
        return jsonify({"error": "Invalid username or password"}), 401""", invalid_cred_replace)

with open("auth.py", "w") as f:
    f.write(content)
