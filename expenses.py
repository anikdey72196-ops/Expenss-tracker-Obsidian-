from imports import (
    Blueprint, request, jsonify, jwt_required, get_jwt_identity,
    math, datetime, timedelta, date, Expense, db
)

expenses_bp = Blueprint('expenses', __name__, url_prefix='/expenses')

VALID_CATEGORIES = [
    'Food & Dining', 'Transport', 'Shopping', 'Utilities', 'Health',
    'Entertainment', 'Education', 'Software', 'Personal Care', 'Investment', 'Other'
]

@expenses_bp.route('', methods=['POST'])
@jwt_required()
def add_expense():
    current_user_id = int(get_jwt_identity())
    data = request.get_json()
    
    if not data or not data.get('amount') or not data.get('category') or not data.get('date'):
        return jsonify({"error": "Amount, category, and date are required"}), 400
        
    if data['category'] not in VALID_CATEGORIES:
        return jsonify({"error": f"Category must be one of: {', '.join(VALID_CATEGORIES)}"}), 400
        
    try:
        expense_date = datetime.datetime.strptime(data['date'], '%Y-%m-%d').date()
    except ValueError:
        return jsonify({"error": "Date must be in YYYY-MM-DD format"}), 400
        
    try:
        amount = float(data['amount'])
        if math.isnan(amount) or math.isinf(amount) or amount < 0 or amount > 1000000000:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "Amount must be a valid number"}), 400
        
    description = data.get('description', '')
    if description and len(description) > 255:
        return jsonify({"error": "Description cannot exceed 255 characters"}), 400

    new_expense = Expense(
        user_id=current_user_id,
        amount=amount,
        category=data['category'],
        date=expense_date,
        description=description
    )
    
    db.session.add(new_expense)
    db.session.commit()
    
    return jsonify(new_expense.to_dict()), 201

@expenses_bp.route('', methods=['GET'])
@jwt_required()
def get_expenses():
    """List and filter past expenses."""
    current_user_id = int(get_jwt_identity())
    filter_type = request.args.get('filter')
    
    query = Expense.query.filter_by(user_id=current_user_id)
    today = date.today()
    
    if filter_type == 'past_week':
        start_date = today - timedelta(days=7)
        query = query.filter(Expense.date >= start_date)
        
    elif filter_type == 'past_month':
        start_date = today - timedelta(days=30)
        query = query.filter(Expense.date >= start_date)
        
    elif filter_type == 'past_3_months':
        start_date = today - timedelta(days=90)
        query = query.filter(Expense.date >= start_date)
        
    elif filter_type == 'custom':
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        if not start_date_str or not end_date_str:
            return jsonify({"error": "start_date and end_date are required for custom filter"}), 400
            
        try:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            query = query.filter(Expense.date >= start_date, Expense.date <= end_date)
        except ValueError:
            return jsonify({"error": "Dates must be in YYYY-MM-DD format"}), 400

    expenses = query.order_by(Expense.date.desc()).all()
    
    return jsonify([expense.to_dict() for expense in expenses]), 200

@expenses_bp.route('/<int:expense_id>', methods=['PUT'])
@jwt_required()
def update_expense(expense_id):
    """Update existing expense."""
    current_user_id = int(get_jwt_identity())
    expense = Expense.query.filter_by(id=expense_id, user_id=current_user_id).first()
    
    if not expense:
        return jsonify({"error": "Expense not found"}), 404
        
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
        
    if 'amount' in data:
        try:
            amount_val = float(data['amount'])
            if math.isnan(amount_val) or math.isinf(amount_val) or amount_val < 0 or amount_val > 1000000000:
                raise ValueError
            expense.amount = amount_val
        except (ValueError, TypeError):
            return jsonify({"error": "Amount must be a valid number"}), 400
        
    if 'category' in data:
        if data['category'] not in VALID_CATEGORIES:
            return jsonify({"error": f"Category must be one of: {', '.join(VALID_CATEGORIES)}"}), 400
        expense.category = data['category']
        
    if 'date' in data:
        try:
            expense.date = datetime.datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({"error": "Date must be in YYYY-MM-DD format"}), 400
            
    if 'description' in data:
        description_val = data.get('description') or ''
        if len(description_val) > 255:
            return jsonify({"error": "Description cannot exceed 255 characters"}), 400
        expense.description = description_val
        
    db.session.commit()
    return jsonify(expense.to_dict()), 200

@expenses_bp.route('/<int:expense_id>', methods=['DELETE'])
@jwt_required()
def delete_expense(expense_id):
    """Remove existing expenses."""
    current_user_id = int(get_jwt_identity())
    expense = Expense.query.filter_by(id=expense_id, user_id=current_user_id).first()
    
    if not expense:
        return jsonify({"error": "Expense not found"}), 404
        
    db.session.delete(expense)
    db.session.commit()
    
    return jsonify({"message": "Expense deleted successfully"}), 200
