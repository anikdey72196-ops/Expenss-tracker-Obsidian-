with open("tests/test_app.py", "r") as f:
    content = f.read()

import_str = """import pytest
from app import app as flask_app, login_attempts as app_login_attempts
from auth import login_attempts as auth_login_attempts
from imports import db, User, Expense"""

content = content.replace("""import pytest
from app import app as flask_app
from imports import db, User, Expense""", import_str)

setup_str = """    with flask_app.app_context():
        db.create_all()

    app_login_attempts.clear()
    auth_login_attempts.clear()

    with flask_app.test_client() as client:"""

content = content.replace("""    with flask_app.app_context():
        db.create_all()

    with flask_app.test_client() as client:""", setup_str)

with open("tests/test_app.py", "w") as f:
    f.write(content)
