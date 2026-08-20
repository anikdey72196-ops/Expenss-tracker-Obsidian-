import re

with open("app.py", "r") as f:
    content = f.read()

# Add to global scope
import_str = """from extensions import db, jwt
import time

login_attempts = {}

def get_client_ip():
    if request.headers.getlist("X-Forwarded-For"):
        return request.headers.getlist("X-Forwarded-For")[0].split(',')[0].strip()
    return request.remote_addr

app = Flask(__name__)"""

content = content.replace("app = Flask(__name__)", import_str)


# Patch login
login_str = """@app.route('/login', methods=['GET', 'POST'])
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
"""

content = content.replace("""@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()""", login_str)

login_fail_str = """                # If the user doesn't exist, or password doesn't match
                if not user or not check_password_hash(user.password_hash, form.password.data):
                    login_attempts[ip].append(current_time)
                    flash("Invalid credentials", "danger")
                    return redirect(url_for('login'))"""

content = content.replace("""                # If the user doesn't exist, or password doesn't match
                if not user or not check_password_hash(user.password_hash, form.password.data):
                    flash("Invalid credentials", "danger")
                    return redirect(url_for('login'))""", login_fail_str)


with open("app.py", "w") as f:
    f.write(content)
