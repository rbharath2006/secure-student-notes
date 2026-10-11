
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
        WTF_CSRF_ENABLED=False,
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
    client.post("/logout")
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


def test_profile_update_rejects_missing_csrf_token(client):
    import app as app_module

    # Keep CSRF disabled while setting up the test account.
    register(client)
    login(client)

    # Enable CSRF validation specifically for the request being tested.
    app_module.app.config["WTF_CSRF_ENABLED"] = True

    try:
        response = client.post(
            "/profile",
            data={"email": "updated@example.com"},
        )
    finally:
        # Restore the fixture's setting for other tests.
        app_module.app.config["WTF_CSRF_ENABLED"] = False

    assert response.status_code == 400



def test_delete_note_rejects_get_request(client):
    register(client)
    login(client)

    response = client.get("/notes/delete/1")

    assert response.status_code == 405


def test_logout_rejects_get_request(client):
    register(client)
    login(client)

    response = client.get("/logout")

    assert response.status_code == 405


def test_registration_stores_hashed_password(client):
    import app as app_module
    from werkzeug.security import check_password_hash

    register(client)

    connection = app_module.get_db_connection()
    try:
        user = connection.execute(
            "SELECT password FROM users WHERE username = ?",
            ("student1",),
        ).fetchone()
    finally:
        connection.close()

    assert user is not None
    assert user["password"] != "TestPass123!"
    assert check_password_hash(user["password"], "TestPass123!")


def test_legacy_plaintext_password_is_upgraded_on_login(client):
    import app as app_module
    from werkzeug.security import check_password_hash

    # Create a user using the existing registration helper.
    register(client)

    # Simulate an account created before password hashing was introduced.
    connection = app_module.get_db_connection()
    try:
        connection.execute(
            "UPDATE users SET password = ? WHERE username = ?",
            ("TestPass123!", "student1"),
        )
        connection.commit()
    finally:
        connection.close()

    # Log in using the legacy plaintext password.
    response = login(client)

    assert response.status_code in (200, 302)

    # Confirm the database now stores a valid password hash.
    connection = app_module.get_db_connection()
    try:
        user = connection.execute(
            "SELECT password FROM users WHERE username = ?",
            ("student1",),
        ).fetchone()
    finally:
        connection.close()

    assert user is not None
    assert user["password"] != "TestPass123!"
    assert check_password_hash(user["password"], "TestPass123!")



def test_user_cannot_delete_another_users_note(client):
    import app as app_module

    # Student 1 creates a note.
    register(client, "student1", "student1@example.com")
    login(client)

    client.post("/notes/create", data={
        "title": "Private note",
        "content": "This note belongs to student1.",
        "category": "Private",
    })

    # Get the note ID from the test database.
    connection = app_module.get_db_connection()
    try:
        note = connection.execute(
            "SELECT id FROM notes WHERE title = ?",
            ("Private note",),
        ).fetchone()
        assert note is not None
        note_id = note["id"]
    finally:
        connection.close()

    # Log out Student 1 and log in Student 2.
    client.post("/logout")
    register(client, "student2", "student2@example.com")
    login(client, "student2")

    # Student 2 attempts to delete Student 1's note.
    response = client.post(f"/notes/delete/{note_id}")

    assert response.status_code == 404

    # Confirm Student 1's note still exists.
    connection = app_module.get_db_connection()
    try:
        remaining_note = connection.execute(
            "SELECT id FROM notes WHERE id = ?",
            (note_id,),
        ).fetchone()
    finally:
        connection.close()

    assert remaining_note is not None



def test_user_can_delete_own_note(client):
    import app as app_module

    register(client)
    login(client)

    client.post("/notes/create", data={
        "title": "My note",
        "content": "This note belongs to me.",
        "category": "Personal",
    })

    connection = app_module.get_db_connection()
    try:
        note = connection.execute(
            "SELECT id FROM notes WHERE title = ?",
            ("My note",),
        ).fetchone()
        assert note is not None
        note_id = note["id"]
    finally:
        connection.close()

    response = client.post(f"/notes/delete/{note_id}")

    assert response.status_code == 200

    connection = app_module.get_db_connection()
    try:
        deleted_note = connection.execute(
            "SELECT id FROM notes WHERE id = ?",
            (note_id,),
        ).fetchone()
    finally:
        connection.close()

    assert deleted_note is None
