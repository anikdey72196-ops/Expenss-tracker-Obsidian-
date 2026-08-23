import time
import logging
from imports import (
    Blueprint, render_template, redirect, session, request, url_for, flash,
    generate_password_hash, check_password_hash, db, User, RegistrationForm, LoginForm
)

logger = logging.getLogger(__name__)
auth_web_bp = Blueprint('auth_web', __name__)
login_attempts = {}

# Rate limit: max 5 failed logins per IP within 300 seconds (5 minutes)
_RATE_LIMIT_MAX = 5
_RATE_LIMIT_WINDOW = 300


def get_client_ip():
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        # Only trust the first IP in the chain
        return xff.split(',')[0].strip()
    return request.remote_addr or "unknown"


@auth_web_bp.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        existing_user = User.query.filter_by(username=form.username.data).first()
        if existing_user:
            flash("Username already exists. Please choose a different one.", "danger")
            return redirect(url_for('auth_web.register'))

        hashed_password = generate_password_hash(form.password.data)
        new_user = User(username=form.username.data, password_hash=hashed_password)

        try:
            db.session.add(new_user)
            db.session.commit()
            flash("Account created successfully! Please log in.", "success")
            return redirect(url_for('auth_web.login'))
        except Exception:
            db.session.rollback()
            logger.exception("DB error creating user '%s'", form.username.data)
            flash("Could not create your account. Please try again later.", "danger")
            return redirect(url_for('auth_web.register'))

    return render_template("register.html", form=form)


@auth_web_bp.route('/login', methods=['GET', 'POST'])
def login():
    ip = get_client_ip()
    attempts, last_time = login_attempts.get(ip, (0, 0))

    if attempts >= _RATE_LIMIT_MAX and time.time() - last_time < _RATE_LIMIT_WINDOW:
        flash("Too many failed login attempts. Please try again in 5 minutes.", "danger")
        return redirect(url_for('auth_web.login'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            session.clear()
            session['user_id'] = user.id
            session['user'] = user.username
            session.permanent = True
            login_attempts.pop(ip, None)  # clear on successful login
            flash("Logged in successfully!", "success")
            return redirect(url_for('expense_web.home'))
        else:
            logger.warning("Failed login attempt from IP %s for username '%s'", ip, form.username.data)
            login_attempts[ip] = (attempts + 1, time.time())
            flash("Invalid username or password.", "danger")
            return redirect(url_for('auth_web.login'))

    return render_template("login.html", form=form)


@auth_web_bp.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully!", "success")
    return redirect(url_for('index'))
