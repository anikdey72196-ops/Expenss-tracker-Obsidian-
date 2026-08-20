from imports import (
    os, math, datetime, urllib, ssl, load_dotenv, NullPool,
    Flask, render_template, redirect, session, request, url_for, flash,
    generate_password_hash, check_password_hash, CSRFProtect,
    db, User, Expense, RegistrationForm, LoginForm , json , requests
)

from extensions import db, jwt
import time

login_attempts = {}

def get_client_ip():
    if request.headers.getlist("X-Forwarded-For"):
        return request.headers.getlist("X-Forwarded-For")[0].split(',')[0].strip()
    return request.remote_addr

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))

DB_USER = os.environ.get('DB_USER', 'root')
DB_PASSWORD_RAW = os.environ.get('DB_PASSWORD', '')
DB_PASSWORD = urllib.parse.quote_plus(DB_PASSWORD_RAW)
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'expense_tracker')
DB_PORT = os.environ.get('DB_PORT', '3306')

is_vercel = os.environ.get('VERCEL') == '1' or os.environ.get('VERCEL_ENV') is not None
is_render = os.environ.get('RENDER') == 'true' or os.environ.get('RENDER_SERVICE_ID') is not None

if os.environ.get('PYTEST_CURRENT_TEST'):
    db_uri = 'sqlite:///:memory:'
elif os.environ.get('DATABASE_URL') and 'dpg-xxx' not in os.environ.get('DATABASE_URL'):
    db_uri = os.environ.get('DATABASE_URL')
    if db_uri.startswith("postgres://"):
        db_uri = db_uri.replace("postgres://", "postgresql://", 1)
elif (is_vercel or is_render) and (os.environ.get('DB_HOST', 'localhost') in ('localhost', '127.0.0.1') or 'dpg-xxx' in os.environ.get('DATABASE_URL', '')):
    # On Render/Vercel with default placeholder DB env vars, fallback cleanly to SQLite in /tmp
    db_uri = 'sqlite:////tmp/expense_tracker.db'
else:
    db_uri = f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'

app.config['SQLALCHEMY_DATABASE_URI'] = db_uri

engine_options = {
    'poolclass': NullPool,
}

if not db_uri.startswith('sqlite') and DB_HOST not in ('localhost', '127.0.0.1'):
    connect_args = {'connect_timeout': 5}
    if os.environ.get('DB_USE_SSL', 'false').lower() == 'true':
        ca_path = '/etc/pki/tls/certs/ca-bundle.crt'
        if not os.path.exists(ca_path):
            import certifi
            ca_path = certifi.where()
        connect_args['ssl'] = {'ca': ca_path}
    engine_options['connect_args'] = connect_args

app.config['SQLALCHEMY_ENGINE_OPTIONS'] = engine_options
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Session security
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

csrf = CSRFProtect(app)
db.init_app(app)

# Register AI Blueprint
from ai_service import ai_bp
app.register_blueprint(ai_bp)
csrf.exempt(ai_bp)  # AI endpoints use JSON, not forms

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

# Ensure app.config overrides are applied before create_all
with app.app_context():
    # If we are testing or running pytest, skip creating db here
    # to avoid connecting to the default mysql db
    if not os.environ.get('PYTEST_CURRENT_TEST') and not app.config.get('TESTING'):
        try:
            db.create_all()
        except Exception as e:
            print(f"Error during db.create_all(): {e}")

GOOD_CATEGORIES = {'Education', 'Health', 'Utilities', 'Software', 'Personal Care','Investment'}
BAD_CATEGORIES = {'Shopping', 'Entertainment', 'Party/junk food'}

CATEGORY_META = {
    'Food & Dining': {'icon': 'restaurant', 'color_class': 'text-violet-400', 'bg_class': 'bg-violet-400/10'},
    'Transport': {'icon': 'commute', 'color_class': 'text-emerald-400', 'bg_class': 'bg-emerald-400/10'},
    'Shopping': {'icon': 'shopping_bag', 'color_class': 'text-pink-400', 'bg_class': 'bg-pink-400/10'},
    'Utilities': {'icon': 'bolt', 'color_class': 'text-primary', 'bg_class': 'bg-primary/20'},
    'Health': {'icon': 'medical_services', 'color_class': 'text-red-400', 'bg_class': 'bg-red-400/10'},
    'Entertainment': {'icon': 'movie', 'color_class': 'text-yellow-400', 'bg_class': 'bg-yellow-400/10'},
    'Education': {'icon': 'school', 'color_class': 'text-blue-400', 'bg_class': 'bg-blue-400/10'},
    'Software': {'icon': 'code', 'color_class': 'text-cyan-400', 'bg_class': 'bg-cyan-400/10'},
    'Personal Care': {'icon': 'spa', 'color_class': 'text-teal-400', 'bg_class': 'bg-teal-400/10'},
    'Investment': {'icon': 'trending_up', 'color_class': 'text-green-400', 'bg_class': 'bg-green-400/10'},
    'Other': {'icon': 'category', 'color_class': 'text-zinc-400', 'bg_class': 'bg-zinc-700/20'},
}

def get_dashboard_stats(expenses):
    if not expenses:
        today = datetime.date.today()
        chart_data = {'labels': [(today - datetime.timedelta(days=i)).strftime('%a').upper() for i in range(6, -1, -1)], 'data': [0.0]*7}
        monthly_chart_data = {'labels': [datetime.date(today.year + (today.month - i - 1) // 12, (today.month - i - 1) % 12 + 1, 1).strftime('%b').upper() for i in range(5, -1, -1)], 'data': [0.0]*6}
        return {
            'overall_score': 5.0,
            'today_score': 50,
            'last_month_total': 0.0,
            'daily_avg_score': 5.0,
            'chart_data': chart_data,
            'monthly_chart_data': monthly_chart_data,
            'category_chart_data': {'labels': [], 'data': []},
            'top_categories': []
        }
        
    overall_score = 5.0
    # Today's Score starts at a fresh 100 points baseline at midnight (12:00 AM) each day
    today_score = 100
    last_month_total = 0.0
    
    today = datetime.date.today()
    try:
        first_of_this_month = today.replace(day=1)
        last_day_last_month = first_of_this_month - datetime.timedelta(days=1)
        first_of_last_month = last_day_last_month.replace(day=1)
    except Exception:
        first_of_last_month = today
        last_day_last_month = today
    
    daily_scores = {}
    
    chart_data = {'labels': [], 'data': []}
    for i in range(6, -1, -1):
        day = today - datetime.timedelta(days=i)
        chart_data['labels'].append(day.strftime('%a').upper())
        chart_data['data'].append(0.0)
        
    monthly_chart_data = {'labels': [], 'data': []}
    for i in range(5, -1, -1):
        m = (today.month - i - 1) % 12 + 1
        y = today.year + (today.month - i - 1) // 12
        monthly_chart_data['labels'].append(datetime.date(y, m, 1).strftime('%b').upper())
        monthly_chart_data['data'].append(0.0)
        
    category_totals = {}
    
    for exp in expenses:
        category = exp.category
        amount = exp.amount
        exp_date = exp.date
            
        if category in GOOD_CATEGORIES:
            overall_score += 1
        elif category in BAD_CATEGORIES:
            overall_score -= 2
            
        # Daily Score: Resets automatically at 12:00 AM Midnight (new date).
        # Only transactions recorded on today's calendar date affect today's score.
        if exp_date == today:
            if category in GOOD_CATEGORIES:
                today_score += 10
            elif category in BAD_CATEGORIES:
                today_score -= 15
                
        
        if first_of_last_month <= exp_date <= last_day_last_month:
            last_month_total += amount
            
        
        if exp_date >= first_of_this_month:
            category_totals[category] = category_totals.get(category, 0) + amount
            
        # Chart Data
        days_ago = (today - exp_date).days
        if 0 <= days_ago <= 6:
            index = 6 - days_ago
            chart_data['data'][index] += amount
            
        # Monthly Chart Data
        months_ago = (today.year - exp_date.year) * 12 + (today.month - exp_date.month)
        if 0 <= months_ago <= 5:
            index = 5 - months_ago
            monthly_chart_data['data'][index] += amount
            
        # Daily tracking for average
        if exp_date not in daily_scores:
            daily_scores[exp_date] = 5.0
        if category in GOOD_CATEGORIES:
            daily_scores[exp_date] += 1
        elif category in BAD_CATEGORIES:
            daily_scores[exp_date] -= 2

    # Clamping scores to bounds
    overall_score = max(0.0, min(10.0, overall_score))
    today_score = max(0, min(100, today_score))
    
    # Calculate daily average score
    if daily_scores:
        avg = sum(max(0.0, min(10.0, s)) for s in daily_scores.values()) / len(daily_scores)
        daily_avg_score = round(avg, 1)
    else:
        daily_avg_score = 5.0
        
    # Process Top Categories
    sorted_cats = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)[:4]
    top_categories = []
    for cat, total in sorted_cats:
        meta = CATEGORY_META.get(cat, CATEGORY_META['Other'])
        top_categories.append({
            'name': cat,
            'amount': round(total, 2),
            'icon': meta['icon'],
            'color_class': meta['color_class'],
            'bg_class': meta['bg_class']
        })

    # Round chart data
    chart_data['data'] = [round(d, 2) for d in chart_data['data']]
    monthly_chart_data['data'] = [round(d, 2) for d in monthly_chart_data['data']]
    
    category_chart_data = {'labels': [], 'data': []}
    # Sort categories by total for the chart
    for cat, total in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
        category_chart_data['labels'].append(cat)
        category_chart_data['data'].append(round(total, 2))

    return {
        'overall_score': round(overall_score, 1),
        'today_score': today_score,
        'last_month_total': round(last_month_total, 2),
        'daily_avg_score': daily_avg_score,
        'chart_data': chart_data,
        'monthly_chart_data': monthly_chart_data,
        'category_chart_data': category_chart_data,
        'top_categories': top_categories
    }


@app.route("/", methods=['GET', 'POST'])
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            try:
                # Store user in database
                existing_user = User.query.filter_by(username=form.username.data).first()
                if existing_user:
                    flash("Username already exists", "danger")
                    return redirect(url_for('register'))
                
                hashed_password = generate_password_hash(form.password.data)
                new_user = User(
                    username=form.username.data,
                    password_hash=hashed_password
                )
                db.session.add(new_user)
                db.session.commit()
                flash("Registered successfully!", "success")
                return redirect(url_for('login'))
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Database Error on {DB_HOST}:{DB_PORT}: {str(e)}")
                flash("An unexpected error occurred during registration. Please try again later.", "danger")
                return redirect(url_for('register'))
    return render_template('register.html', form=form)
    
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()

    ip = get_client_ip()
    current_time = time.time()

    if len(login_attempts) > 1000:
        login_attempts.clear()

    attempts = login_attempts.get(ip, [])
    attempts = [t for t in attempts if current_time - t < 300]

    if len(attempts) >= 5:
        flash("Too many login attempts. Please try again later.", "danger")
        return render_template('login.html', form=form)

    login_attempts[ip] = attempts

    if request.method == 'POST':
        if form.validate_on_submit():
            try:
                # Find the user by their username
                user = User.query.filter_by(username=form.username.data).first()
                
                # If the user doesn't exist, or password doesn't match
                if not user or not check_password_hash(user.password_hash, form.password.data):
                    login_attempts[ip].append(current_time)
                    flash("Invalid credentials", "danger")
                    return redirect(url_for('login'))
                
                # If successful
                session['user_id'] = user.id
                session['user'] = user.username
                flash("Logged in successfully!", "success")
                return redirect(url_for('home'))
            except Exception as e:
                app.logger.error(f"Database Error on {DB_HOST}:{DB_PORT}: {str(e)}")
                flash("An unexpected error occurred during login. Please try again later.", "danger")
                return redirect(url_for('login'))
    return render_template('login.html', form=form)

def _safe_stats(raw_stats):
    """
    Ensure the stats dict always contains every key the Jinja2 template depends on,
    with safe numeric/list defaults.  This prevents a silent Jinja2 crash when
    `stats` is missing a key, which causes math operations like
    ``{{ stats.overall_score * 10 }}`` to raise a TypeError that silently swallows
    all HTML inside the surrounding grid container.
    """
    today = datetime.date.today()
    _default_chart = {
        'labels': [(today - datetime.timedelta(days=i)).strftime('%a').upper() for i in range(6, -1, -1)],
        'data': [0.0] * 7,
    }
    _default_monthly = {
        'labels': [
            datetime.date(
                today.year + (today.month - i - 1) // 12,
                (today.month - i - 1) % 12 + 1,
                1,
            ).strftime('%b').upper()
            for i in range(5, -1, -1)
        ],
        'data': [0.0] * 6,
    }
    defaults = {
        'overall_score': 5.0,
        'today_score': 50,
        'last_month_total': 0.0,
        'daily_avg_score': 5.0,
        'chart_data': _default_chart,
        'monthly_chart_data': _default_monthly,
        'category_chart_data': {'labels': [], 'data': []},
        'top_categories': [],
    }
    if not isinstance(raw_stats, dict):
        return defaults
    merged = {**defaults, **raw_stats}
    # Guarantee numeric types so Jinja2 math never raises TypeError
    merged['overall_score'] = float(merged['overall_score'] or 0.0)
    merged['today_score'] = int(merged['today_score'] or 0)
    merged['last_month_total'] = float(merged['last_month_total'] or 0.0)
    merged['daily_avg_score'] = float(merged['daily_avg_score'] or 0.0)
    # Guarantee top_categories is always a list, never None
    if not isinstance(merged['top_categories'], list):
        merged['top_categories'] = []
    return merged


@app.route('/home', methods=['GET'])
def home():
    if 'user_id' not in session:
        flash("Please login first", "danger")
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    expenses = []
    expenses_list = []
    try:
        expenses = Expense.query.filter_by(user_id=user_id).order_by(Expense.date.desc()).all()
        expenses_list = [exp.to_dict() for exp in expenses]
    except Exception as e:
        app.logger.error(f"DB error loading expenses for user {user_id}: {e}")
        flash("Could not load your expenses. Please try again later.", "danger")

    # Compute stats from ORM objects; _safe_stats guarantees all required keys
    # are present with valid numeric/list defaults so Jinja2 math never crashes.
    raw_stats = get_dashboard_stats(expenses)
    stats = _safe_stats(raw_stats)

    return render_template('home.html', username=session['user'], expenses=expenses_list, stats=stats)

@app.route('/history', methods=['GET'])
def history():
    if 'user_id' not in session:
        flash("Please login first", "danger")
        return redirect(url_for('login'))
        
    user_id = session.get('user_id')
    query = Expense.query.filter_by(user_id=user_id)
    
    filter_type = request.args.get('filter', 'all')
    category_filter = request.args.get('category', 'all')
    search_query = request.args.get('search', '').strip()
    sort_order = request.args.get('sort', 'date_desc')
    start_date_str = request.args.get('start_date', '')
    end_date_str = request.args.get('end_date', '')
    
    today = datetime.date.today()
    
    # Date Filtering
    if filter_type == 'past_week':
        query = query.filter(Expense.date >= today - datetime.timedelta(days=7))
    elif filter_type == 'past_month':
        query = query.filter(Expense.date >= today - datetime.timedelta(days=30))
    elif filter_type == 'past_3_months':
        query = query.filter(Expense.date >= today - datetime.timedelta(days=90))
    elif filter_type == 'custom':
        if start_date_str:
            try:
                s_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
                query = query.filter(Expense.date >= s_date)
            except ValueError:
                pass
        if end_date_str:
            try:
                e_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
                query = query.filter(Expense.date <= e_date)
            except ValueError:
                pass
                
    # Category Filtering
    if category_filter and category_filter != 'all':
        query = query.filter(Expense.category == category_filter)
        
    # Search Query
    if search_query:
        query = query.filter(
            (Expense.description.ilike(f"%{search_query}%")) |
            (Expense.category.ilike(f"%{search_query}%"))
        )
        
    # Sorting
    if sort_order == 'date_asc':
        query = query.order_by(Expense.date.asc(), Expense.id.asc())
    elif sort_order == 'amount_desc':
        query = query.order_by(Expense.amount.desc(), Expense.date.desc())
    elif sort_order == 'amount_asc':
        query = query.order_by(Expense.amount.asc(), Expense.date.desc())
    else:  # date_desc default
        query = query.order_by(Expense.date.desc(), Expense.id.desc())
        
    expenses = query.all()
    expenses_list = [exp.to_dict() for exp in expenses]
    
    total_amount = sum(exp.amount for exp in expenses)
    count = len(expenses)
    avg_amount = total_amount / count if count > 0 else 0.0
    
    categories = list(CATEGORY_META.keys())
    
    stats = {
        'total_amount': round(total_amount, 2),
        'count': count,
        'avg_amount': round(avg_amount, 2)
    }
    
    return render_template(
        'history.html',
        username=session['user'],
        expenses=expenses_list,
        categories=categories,
        stats=stats,
        filter_type=filter_type,
        category_filter=category_filter,
        search_query=search_query,
        sort_order=sort_order,
        start_date=start_date_str,
        end_date=end_date_str
    )

@app.route('/addexpense', methods=['GET', 'POST'])
def addexpense():
    if 'user_id' not in session:
        flash("Please login first", "danger")
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Retrieve form data
        amount = request.form.get('amount')
        category = request.form.get('category')
        date_str = request.form.get('date') 
        description = request.form.get('description', '')
        
        if category and len(category) > 50:
            flash("Category is too long", "danger")
            return redirect(url_for('addexpense'))

        if description and len(description) > 255:
            flash("Description is too long", "danger")
            return redirect(url_for('addexpense'))

        try:
            amount_val = float(amount)
            if math.isnan(amount_val) or math.isinf(amount_val) or amount_val < 0 or amount_val > 1000000000:
                raise ValueError
        except (ValueError, TypeError):
            flash("Invalid amount", "danger")
            return redirect(url_for('addexpense'))
            
        try:
            exp_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            exp_date = datetime.date.today()
        
        new_expense = Expense(
            user_id=session['user_id'],
            amount=amount_val,
            category=category,
            date=exp_date,
            description=description
        )
        db.session.add(new_expense)
        db.session.commit()
        
        flash("Expense added successfully!", "success")
        return redirect(url_for('home'))
        
    today_date = datetime.date.today().strftime('%Y-%m-%d')
    return render_template('add_expense.html', today_date=today_date)

@app.route('/edit_expense/<int:id>', methods=['GET', 'POST'])
def edit_expense(id):
    if 'user_id' not in session:
        flash("Please login first", "danger")
        return redirect(url_for('login'))
        
    # Get the specific expense
    expense = Expense.query.filter_by(id=id, user_id=session['user_id']).first()
    if not expense:
        flash("Expense not found", "danger")
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        amount = request.form.get('amount')
        category = request.form.get('category')
        date_str = request.form.get('date')
        description = request.form.get('description', '')
        
        if category and len(category) > 50:
            flash("Category is too long", "danger")
            return redirect(url_for('edit_expense', id=id))

        if description and len(description) > 255:
            flash("Description is too long", "danger")
            return redirect(url_for('edit_expense', id=id))

        try:
            amount_val = float(amount)
            if math.isnan(amount_val) or math.isinf(amount_val) or amount_val < 0 or amount_val > 1000000000:
                raise ValueError
            expense.amount = amount_val
        except (ValueError, TypeError):
            flash("Invalid amount", "danger")
            return redirect(url_for('edit_expense', id=id))
            
        expense.category = category
        try:
            expense.date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            pass # keep original if invalid
            
        expense.description = description
        db.session.commit()
        
        flash("Expense updated successfully!", "success")
        return redirect(url_for('home'))
        
    return render_template("edit.html", expense=expense.to_dict())

@app.route('/delete_expense/<int:id>', methods=['POST'])
def delete_expense(id):
    if 'user_id' not in session:
        flash("Please login first", "danger")
        return redirect(url_for('login'))
        
    expense = Expense.query.filter_by(id=id, user_id=session['user_id']).first()
    if expense:
        db.session.delete(expense)
        db.session.commit()
        flash("Expense deleted successfully!", "success")
    else:
        flash("Expense not found or could not be deleted.", "danger")
        
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully!", "success")
    return redirect(url_for('index'))

@app.route('/admin')
def admin_panel():

    admin_user = os.environ.get('ADMIN_USERNAME')
    admin_key = os.environ.get('ADMIN_SECRET_KEY')
    
    key = request.args.get('key')
    current_user = session.get('user')
    
    if not session.get('user_id') or not admin_user or not (current_user == admin_user or (admin_key and key == admin_key)):
        flash("Access Denied: Administrator permissions required.", "danger")
        return redirect(url_for('home'))
        
    users = User.query.all()
    all_expenses = Expense.query.order_by(Expense.id.desc()).all()
    expenses_data = []
    for exp in all_expenses:
        expenses_data.append({
            'id': exp.id,
            'username': exp.user.username if exp.user else 'Unknown',
            'category': exp.category,
            'amount': exp.amount,
            'date': exp.date.strftime('%Y-%m-%d') if exp.date else '--',
            'description': exp.description
        })
    return render_template('admin.html', users=users, expenses=expenses_data, total_users=len(users), total_expenses=len(all_expenses))

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    app.run(debug=debug_mode)