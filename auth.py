from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token
from models import User
from extensions import db

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"error": "Username and password are required"}), 400

    if not isinstance(data['username'], str) or len(data['username']) > 80:
        return jsonify({"error": "Username must be between 3 and 80 characters."}), 400

    if not isinstance(data['password'], str) or len(data['password']) > 72:
        return jsonify({"error": "Password must be between 8 and 72 characters."}), 400

    username = data.get('username', '')
    password = data.get('password', '')

    if len(username) < 3 or len(username) > 80:
        return jsonify({"error": "Username must be between 3 and 80 characters."}), 400

    if len(password) < 8 or len(password) > 72:
        return jsonify({"error": "Password must be between 8 and 72 characters."}), 400
    
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 400
        
    hashed_password = generate_password_hash(data['password'])
    new_user = User(username=data['username'], password_hash=hashed_password)
    
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({"message": "User created successfully"}), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate and generate JWT."""
    data = request.get_json()
    
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"error": "Username and password are required"}), 400
        
    if not isinstance(data['username'], str) or not isinstance(data['password'], str) or len(data['username']) > 80 or len(data['password']) > 72:
        return jsonify({"error": "Invalid username or password"}), 401

    user = User.query.filter_by(username=data['username']).first()
    
    if not user or not check_password_hash(user.password_hash, data['password']):
        return jsonify({"error": "Invalid username or password"}), 401
        
    # Generate token using user ID
    access_token = create_access_token(identity=str(user.id))
    return jsonify(access_token=access_token), 200
