import time
from imports import (
    Blueprint, render_template, redirect, session, request, url_for, flash,
    generate_password_hash, check_password_hash, db, User, RegistrationForm, LoginForm
)

auth_web_bp = Blueprint('auth_web', __name__)
login_attempts = {}


def get_client_ip():
    if request.headers.getlist("X-Forwarded-For"):
        return request.headers.getlist("X-Forwarded-For")[0].split(',')[0].strip()
    return request.remote_addr


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
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating user account: {e}", "danger")
            return redirect(url_for('auth_web.register'))

    return render_template("register.html", form=form)


@auth_web_bp.route('/login', methods=['GET', 'POST'])
def login():
    ip = get_client_ip()
    attempts, last_time = login_attempts.get(ip, (0, 0))

    if attempts >= 5 and time.time() - last_time < 300:
        flash("Too many failed attempts. Please try again in 5 minutes.", "danger")
        return redirect(url_for('auth_web.login'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            session.clear()
            session['user_id'] = user.id
            session['user'] = user.username
            session.permanent = True
            login_attempts[ip] = (0, 0)
            flash("Logged in successfully!", "success")
            return redirect(url_for('expense_web.home'))
        else:
            login_attempts[ip] = (attempts + 1, time.time())
            flash("Invalid username or password.", "danger")
            return redirect(url_for('auth_web.login'))

    return render_template("login.html", form=form)


@auth_web_bp.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully!", "success")
    return redirect(url_for('index'))
