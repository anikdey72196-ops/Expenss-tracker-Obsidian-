import os
import hmac
from imports import Blueprint, render_template, redirect, session, request, url_for, flash, User, Expense

admin_web_bp = Blueprint('admin_web', __name__)


@admin_web_bp.route('/admin')
def admin_panel():
    admin_user = os.environ.get('ADMIN_USERNAME')
    admin_key = os.environ.get('ADMIN_SECRET_KEY')

    key = request.args.get('key')
    current_user = session.get('user')

    is_user_match = bool(current_user and admin_user and hmac.compare_digest(current_user.encode('utf-8'), admin_user.encode('utf-8')))
    is_key_match = bool(key and admin_key and hmac.compare_digest(key.encode('utf-8'), admin_key.encode('utf-8')))

    if not session.get('user_id') or not (is_user_match or is_key_match):
        flash("Access Denied: Administrator permissions required.", "danger")
        return redirect(url_for('expense_web.home'))

    users = User.query.all()
    user_data = []
    total_system_expenses = 0

    for u in users:
        user_expenses = Expense.query.filter_by(user_id=u.id).order_by(Expense.date.desc()).all()
        exp_list = []
        user_total = 0.0
        for exp in user_expenses:
            user_total += exp.amount
            exp_list.append({
                'id': exp.id,
                'category': exp.category,
                'amount': exp.amount,
                'date': exp.date.strftime('%Y-%m-%d') if exp.date else '--',
                'description': exp.description or 'No description'
            })

        total_system_expenses += len(exp_list)
        user_data.append({
            'id': u.id,
            'username': u.username,
            'total_spent': round(user_total, 2),
            'expense_count': len(exp_list),
            'expenses': exp_list
        })

    return render_template('admin.html', user_data=user_data, total_users=len(users), total_expenses=total_system_expenses)
