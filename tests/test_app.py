import os
os.environ['PYTEST_CURRENT_TEST'] = 'true'
import pytest
from app import app as flask_app
from extensions import db
from models import User, Expense

@pytest.fixture
def client():
    # Configure app for testing
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    # Also override ENGINE_OPTIONS for testing with sqlite
    flask_app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {}

    # Setup database
    with flask_app.app_context():
        db.create_all()

    with flask_app.test_client() as client:
        yield client
        
    # Teardown database
    with flask_app.app_context():
        db.drop_all()

def test_index_page(client):
    response = client.get("/")
    assert response.status_code == 200

def test_register_page_get(client):
    response = client.get("/register")
    assert response.status_code == 200

def test_register_page_post(client):
    response = client.post("/register", data={
        "username": "testuser",
        "password": "testpassword",
        "submit": "Sign Up"
    })
    # Should redirect to login on successful registration
    assert response.status_code == 302
    assert response.headers["Location"] == "/login"

def test_login_page_get(client):
    response = client.get("/login")
    assert response.status_code == 200

def test_login_page_post_invalid(client):
    response = client.post("/login", data={
        "username": "wronguser",
        "password": "wrongpassword",
        "submit": "Sign In"
    })
    # Redirects back to login on failure (flash message shown)
    assert response.status_code == 302
    assert response.headers["Location"] == "/login"

def test_login_page_post_valid(client):
    # First register a user
    client.post("/register", data={
        "username": "testuser",
        "password": "testpassword",
        "submit": "Sign Up"
    })

    # Then login
    response = client.post("/login", data={
        "username": "testuser",
        "password": "testpassword",
        "submit": "Sign In"
    })

    # Redirects to home on success
    assert response.status_code == 302
    assert response.headers["Location"] == "/home"

def test_logout(client):
    response = client.get("/logout")
    assert response.status_code == 302
    assert response.headers["Location"] == "/"

def test_protected_routes_unauthenticated(client):
    routes = ["/home", "/addexpense", "/edit_expense/1"]
    for route in routes:
        response = client.get(route)
        assert response.status_code == 302
        assert response.headers["Location"] == "/login"

    # Delete requires POST
    response = client.post("/delete_expense/1")
    assert response.status_code == 302
    assert response.headers["Location"] == "/login"

def test_home_authenticated(client):
    # Register and login
    client.post("/register", data={"username": "testuser", "password": "testpassword", "submit": "Sign Up"})
    client.post("/login", data={"username": "testuser", "password": "testpassword", "submit": "Sign In"})

    response = client.get("/home")
    assert response.status_code == 200

def test_add_expense_authenticated(client):
    client.post("/register", data={"username": "testuser", "password": "testpassword", "submit": "Sign Up"})
    client.post("/login", data={"username": "testuser", "password": "testpassword", "submit": "Sign In"})

    # Add expense POST
    response = client.post("/addexpense", data={
        "amount": "100.50",
        "category": "Education",
        "date": "2024-01-01",
        "description": "Books"
    })
    # Should redirect to home
    assert response.status_code == 302
    assert response.headers["Location"] == "/home"

def test_edit_delete_expense_authenticated(client):
    client.post("/register", data={"username": "testuser", "password": "testpassword", "submit": "Sign Up"})
    client.post("/login", data={"username": "testuser", "password": "testpassword", "submit": "Sign In"})

    # Add expense via API to get an ID
    client.post("/addexpense", data={
        "amount": "100.50",
        "category": "Education",
        "date": "2024-01-01",
        "description": "Books"
    })
    
    with flask_app.app_context():
        expense = Expense.query.filter_by(description="Books").first()
        expense_id = expense.id

    # Edit expense GET
    response = client.get(f"/edit_expense/{expense_id}")
    assert response.status_code == 200

    # Edit expense POST
    response = client.post(f"/edit_expense/{expense_id}", data={
        "amount": "200.00",
        "category": "Health",
        "date": "2024-01-02",
        "description": "Medicine"
    })
    assert response.status_code == 302
    assert response.headers["Location"] == "/home"

    # Check if updated in DB
    with flask_app.app_context():
        updated_expense = Expense.query.get(expense_id)
        assert updated_expense.amount == 200.0

    # Delete expense
    response = client.post(f"/delete_expense/{expense_id}")
    assert response.status_code == 302
    assert response.headers["Location"] == "/home"

    # Check if deleted in DB
    with flask_app.app_context():
        deleted_expense = Expense.query.get(expense_id)
        assert deleted_expense is None

def test_register_oversized_payloads(client):
    # Test oversized username
    response = client.post("/register", data={
        "username": "a" * 81,
        "password": "validpassword",
        "submit": "Sign Up"
    })
    assert response.status_code == 200 # Form validation fails and re-renders form
    assert b"Username must be between 3 and 80 characters." in response.data

    # Test oversized password
    response = client.post("/register", data={
        "username": "validuser",
        "password": "a" * 129,
        "submit": "Sign Up"
    })
    assert response.status_code == 200
    assert b"Password must be between 8 and 72 characters." in response.data

def test_api_signup_oversized_payloads():
    import os
    # create_app() reads PYTEST_CURRENT_TEST and then DB_* env vars to construct db_uri.
    # Let's just override it immediately after creation.
    os.environ['PYTEST_CURRENT_TEST'] = 'true'
    from expense_api import create_app
    api_app = create_app()
    api_app.config['TESTING'] = True
    api_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    api_app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {}

    with api_app.app_context():
        db.create_all()

    with api_app.test_client() as api_client:
        # Test oversized username in API
        response = api_client.post("/auth/signup", json={
            "username": "a" * 81,
            "password": "validpassword"
        })
        assert response.status_code == 400
        assert response.get_json()["error"] == "Username must be between 3 and 80 characters."

        # Test oversized password in API
        response = api_client.post("/auth/signup", json={
            "username": "validuser",
            "password": "a" * 129
        })
        assert response.status_code == 400
        assert response.get_json()["error"] == "Password must be between 8 and 72 characters."

    with api_app.app_context():
        db.drop_all()

def test_add_invalid_amount(client):
    client.post("/register", data={"username": "testuser_amt", "password": "testpassword", "submit": "Sign Up"})
    client.post("/login", data={"username": "testuser_amt", "password": "testpassword", "submit": "Sign In"})

    invalid_amounts = ['-100', 'inf', 'nan', '1e10', 'abc']
    for amt in invalid_amounts:
        response = client.post("/addexpense", data={
            "amount": amt,
            "category": "Education",
            "date": "2024-01-01",
            "description": "Books"
        })
        # Should redirect back to addexpense or not crash, but expense should not be added
        assert response.status_code == 302

    with flask_app.app_context():
        user = User.query.filter_by(username="testuser_amt").first()
        expenses = Expense.query.filter_by(user_id=user.id).all()
        assert len(expenses) == 0

def test_register_long_username(client):
    # Should not crash with a 500 error if username is > 80 chars
    long_username = "a" * 81
    response = client.post("/register", data={
        "username": long_username,
        "password": "testpassword",
        "submit": "Sign Up"
    })

    # Validation failed in WTForms, should render template again (200 OK) with errors
    assert response.status_code == 200
    assert b"Field cannot be longer than 80 characters" in response.data or b"Invalid" in response.data or b"Register" in response.data
