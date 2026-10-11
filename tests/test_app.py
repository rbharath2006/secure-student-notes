
import sqlite3

import pytest
import app as app_module


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Give every test its own temporary SQLite database."""
    db_path = tmp_path / "test_notes.db"

    connection = sqlite3.connect(db_path)
    connection.executescript("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        );

        CREATE TABLE notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (note_id) REFERENCES notes(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    connection.commit()
    connection.close()

    def test_connection():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(
        app_module, "get_db_connection", test_connection
    )

    app_module.app.config.update(
        TESTING=True,
        SECRET_KEY="test-only-secret-key",
    )

    with app_module.app.test_client() as test_client:
        yield test_client


def register(client, username="student1", email="student1@example.com",
             password="TestPass123!"):
    return client.post("/register", data={
        "username": username,
        "email": email,
        "password": password,
    })


def login(client, username="student1", password="TestPass123!"):
    return client.post("/login", data={
        "username": username,
        "password": password,
    })


def test_home_page_loads(client):
    response = client.get("/")
    assert response.status_code == 200


def test_registration_succeeds(client):
    response = register(client)

    assert response.status_code == 200
    assert b"Registration successful" in response.data


def test_login_and_dashboard(client):
    register(client)

    response = login(client, password="TestPass123!",)

    assert response.status_code == 302
    assert "/dashboard" in response.headers["Location"]

    response = client.get("/dashboard")
    assert response.status_code == 200


def test_dashboard_requires_login(client):
    response = client.get("/dashboard")

    assert response.status_code == 401
    assert b"Sign in required" in response.data


def test_login_rejects_sql_injection_payload(client):
    register(client)

    response = login(
        client,
        username="' OR '1'='1' --",
        password="anything",
    )

    assert response.status_code == 401
    assert b"student1" not in response.data


def test_create_and_search_note(client):
    register(client)
    login(client)

    response = client.post("/notes/create", data={
        "title": "Cybersecurity Revision",
        "content": "Study SQL injection and XSS.",
        "category": "Study",
    })

    assert response.status_code == 200
    assert b"Note created successfully" in response.data

    response = client.get("/search?q=Cybersecurity")

    assert response.status_code == 200
    assert b"Cybersecurity Revision" in response.data


def test_user_cannot_edit_another_users_note(client):
    register(client, "student1", "student1@example.com")
    login(client)

    client.post("/notes/create", data={
        "title": "Private note",
        "content": "Only student1 should edit this.",
        "category": "Private",
    })

    # Sign out and create a second account.
    client.get("/logout")
    register(client, "student2", "student2@example.com")
    login(client, "student2")

    # The first user's note has ID 1 in this isolated test database.
    response = client.get("/notes/edit/1")

    assert response.status_code == 404


def test_comment_xss_payload_is_html_escaped(client):
    register(client)
    login(client)

    client.post("/notes/create", data={
        "title": "XSS test note",
        "content": "Testing safe HTML rendering.",
        "category": "Security",
    })

    payload = "<script>alert(1)</script>"

    response = client.post(
        "/notes/1/comments",
        data={"content": payload},
    )

    assert response.status_code == 200
    assert b"&lt;script&gt;alert(1)&lt;/script&gt;" in response.data
    assert payload.encode() not in response.data


def test_profile_post_accepts_request_without_csrf_token(client):
    register(client)
    login(client)

    response = client.post("/profile", data={
        "email": "updated@example.com",
    })

    assert response.status_code == 200
    assert b"updated@example.com" in response.data
