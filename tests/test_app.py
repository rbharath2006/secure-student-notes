
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
        conn.execute("PRAGMA foreign_keys = ON")
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



def post_without_csrf(client, url, data=None):
    """Test that a POST request without a CSRF token is rejected."""
    import app as app_module

    previous_value = app_module.app.config.get("WTF_CSRF_ENABLED", False)
    app_module.app.config["WTF_CSRF_ENABLED"] = True

    try:
        return client.post(url, data=data or {})
    finally:
        app_module.app.config["WTF_CSRF_ENABLED"] = previous_value



def test_home_page_loads(client):
    response = client.get("/")
    assert response.status_code == 200


def test_registration_succeeds(client):
    response = register(client)

    assert response.status_code == 200
    assert b"Registration successful" in response.data



def test_registration_rejects_invalid_username(client):
    response = register(client, username="ab")

    assert response.status_code == 400
    assert b"Username must be" in response.data


def test_registration_rejects_invalid_email(client):
    response = register(client, email="not-an-email")

    assert response.status_code == 400
    assert b"valid email address" in response.data


def test_registration_rejects_short_password(client):
    response = register(client, password="Short123!")

    assert response.status_code == 400
    assert b"12 and 128 characters" in response.data


def test_registration_rejects_long_password(client):
    response = register(client, password="A" * 129)

    assert response.status_code == 400
    assert b"12 and 128 characters" in response.data


def test_invalid_registration_does_not_create_account(client):
    import app as app_module

    response = register(
        client,
        username="student1",
        email="not-an-email",
    )

    assert response.status_code == 400

    connection = app_module.get_db_connection()
    try:
        user = connection.execute(
            "SELECT id FROM users WHERE username = ?",
            ("student1",),
        ).fetchone()
    finally:
        connection.close()

    assert user is None


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


def test_create_note_rejects_empty_title(client):
    register(client)
    login(client)

    response = client.post("/notes/create", data={
        "title": "   ",
        "content": "Some note content",
        "category": "Study",
    })

    assert response.status_code == 400
    assert b"title is required" in response.data


def test_create_note_rejects_empty_content(client):
    register(client)
    login(client)

    response = client.post("/notes/create", data={
        "title": "My note",
        "content": "   ",
        "category": "Study",
    })

    assert response.status_code == 400
    assert b"content is required" in response.data


def test_create_note_rejects_long_title(client):
    register(client)
    login(client)

    response = client.post("/notes/create", data={
        "title": "A" * 151,
        "content": "Some note content",
        "category": "Study",
    })

    assert response.status_code == 400
    assert b"150 characters or fewer" in response.data


def test_create_note_rejects_long_content(client):
    register(client)
    login(client)

    response = client.post("/notes/create", data={
        "title": "My note",
        "content": "A" * 10001,
        "category": "Study",
    })

    assert response.status_code == 400
    assert b"10,000 characters or fewer" in response.data


def test_create_note_rejects_long_category(client):
    register(client)
    login(client)

    response = client.post("/notes/create", data={
        "title": "My note",
        "content": "Some note content",
        "category": "A" * 51,
    })

    assert response.status_code == 400
    assert b"50 characters or fewer" in response.data


def test_edit_note_rejects_long_title(client):
    register(client)
    login(client)

    client.post("/notes/create", data={
        "title": "My note",
        "content": "Some note content",
        "category": "Study",
    })

    response = client.post("/notes/edit/1", data={
        "title": "A" * 151,
        "content": "Updated content",
        "category": "Study",
    })

    assert response.status_code == 400
    assert b"150 characters or fewer" in response.data


def test_edit_note_rejects_long_content(client):
    register(client)
    login(client)

    client.post("/notes/create", data={
        "title": "My note",
        "content": "Some note content",
        "category": "Study",
    })

    response = client.post("/notes/edit/1", data={
        "title": "My note",
        "content": "A" * 10001,
        "category": "Study",
    })

    assert response.status_code == 400
    assert b"10,000 characters or fewer" in response.data


def test_edit_note_rejects_long_category(client):
    register(client)
    login(client)

    client.post("/notes/create", data={
        "title": "My note",
        "content": "Some note content",
        "category": "Study",
    })

    response = client.post("/notes/edit/1", data={
        "title": "My note",
        "content": "Updated content",
        "category": "A" * 51,
    })

    assert response.status_code == 400
    assert b"50 characters or fewer" in response.data



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



def test_user_cannot_view_another_users_note_comments(client):
    import app as app_module

    # Student 1 creates a private note.
    register(client)
    login(client)
    client.post(
        "/notes/create",
        data={
            "title": "Private note",
            "content": "Student 1 private content",
            "category": "Personal",
        },
    )

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

    # Switch to Student 2.
    client.post("/logout")
    register(
        client,
        username="student2",
        email="student2@example.com",
        password="TestPass123!",
    )
    login(client, username="student2")

        # Make the request as Student 2.
    response = client.get(f"/notes/{note_id}/comments")

    assert response.status_code == 404
    assert b"Student 1 private content" not in response.data



def test_user_cannot_comment_on_another_users_note(client):
    import app as app_module

    # Student 1 creates a private note.
    register(client)
    login(client)
    client.post(
        "/notes/create",
        data={
            "title": "Private note",
            "content": "Student 1 private content",
            "category": "Personal",
        },
    )

    connection = app_module.get_db_connection()
    try:
        note = connection.execute(
            "SELECT id FROM notes WHERE title = ?",
            ("Private note",),
        ).fetchone()
        assert note is not None
        note_id = note["id"]

        comments_before = connection.execute(
            "SELECT COUNT(*) AS total FROM comments WHERE note_id = ?",
            (note_id,),
        ).fetchone()["total"]
    finally:
        connection.close()

    # Switch to Student 2.
    client.post("/logout")
    register(
        client,
        username="student2",
        email="student2@example.com",
        password="TestPass123!",
    )
    login(client, username="student2")

    response = client.post(
        f"/notes/{note_id}/comments",
        data={"content": "Unauthorized comment"},
    )

    assert response.status_code == 404

    # Confirm that no unauthorized comment was saved.
    connection = app_module.get_db_connection()
    try:
        comments_after = connection.execute(
            "SELECT COUNT(*) AS total FROM comments WHERE note_id = ?",
            (note_id,),
        ).fetchone()["total"]
    finally:
        connection.close()

    assert comments_after == comments_before


def test_login_rejects_missing_csrf_token(client):
    import app as app_module

    app_module.app.config["WTF_CSRF_ENABLED"] = True

    try:
        response = client.post(
            "/login",
            data={
                "username": "student1",
                "password": "TestPass123!",
            },
        )
    finally:
        app_module.app.config["WTF_CSRF_ENABLED"] = False

    assert response.status_code == 400





def test_login_accepts_valid_csrf_token(client):
    import re
    import app as app_module

    app_module.app.config["WTF_CSRF_ENABLED"] = True

    try:
        page = client.get("/login")
        assert page.status_code == 200

        html = page.get_data(as_text=True)

        match = re.search(
            r'<input\b(?=[^>]*\bname=["\']csrf_token["\'])'
            r'(?=[^>]*\bvalue=["\']([^"\']+)["\'])[^>]*>',
            html,
            re.IGNORECASE,
        )

        assert match is not None, (
            "Login form must contain a CSRF token input with a value"
        )

        token = match.group(1)

        response = client.post(
            "/login",
            data={
                "username": "nonexistent-user",
                "password": "WrongPassword123!",
                "csrf_token": token,
            },
        )

        # A valid token should pass CSRF validation.
        # Invalid credentials should be handled by the login route.
        assert response.status_code != 400

    finally:
        app_module.app.config["WTF_CSRF_ENABLED"] = False



def test_profile_rejects_empty_email(client):
    register(client)
    login(client)

    response = client.post(
        "/profile",
        data={"email": ""},
    )

    assert response.status_code == 200
    assert b"Please enter a valid email address." in response.data


def test_profile_rejects_invalid_email(client):
    register(client)
    login(client)

    response = client.post(
        "/profile",
        data={"email": "invalid-email"},
    )

    assert response.status_code == 200
    assert b"Please enter a valid email address." in response.data


def test_profile_rejects_email_longer_than_254_characters(client):
    register(client)
    login(client)

    long_email = "a" * 243 + "@example.com"
    assert len(long_email) > 254

    response = client.post(
        "/profile",
        data={"email": long_email},
    )

    assert response.status_code == 200
    assert b"Please enter a valid email address." in response.data


def test_profile_accepts_valid_email(client):
    register(client)
    login(client)

    response = client.post(
        "/profile",
        data={"email": "updated@example.com"},
    )

    assert response.status_code == 200
    assert b"updated@example.com" in response.data




def test_registration_rejects_missing_csrf_token(client):
    response = post_without_csrf(
        client,
        "/register",
        data={
            "username": "csrfstudent",
            "email": "csrfstudent@example.com",
            "password": "TestPass123!",
        },
    )

    assert response.status_code == 400




def test_create_note_rejects_missing_csrf_token(client):
    register(client)
    login(client)

    response = post_without_csrf(
        client,
        "/notes/create",
        data={
            "title": "CSRF test note",
            "content": "This note should not be created.",
            "category": "Testing",
        },
    )

    assert response.status_code == 400



def test_edit_note_rejects_missing_csrf_token(client):
    register(client)
    login(client)

    # Create a note while CSRF is disabled by the test fixture.
    create_response = client.post(
        "/notes/create",
        data={
            "title": "Original title",
            "content": "Original content",
            "category": "Testing",
        },
    )
    assert create_response.status_code == 200

    response = post_without_csrf(
        client,
        "/notes/edit/1",
        data={
            "title": "Changed title",
            "content": "Changed content",
            "category": "Testing",
        },
    )

    assert response.status_code == 400





def test_comment_rejects_missing_csrf_token(client):
    register(client)
    login(client)

    client.post(
        "/notes/create",
        data={
            "title": "Comment test note",
            "content": "Testing CSRF protection for comments.",
            "category": "Testing",
        },
    )

    response = post_without_csrf(
        client,
        "/notes/1/comments",
        data={"content": "This comment should not be added."},
    )

    assert response.status_code == 400



def test_delete_note_rejects_missing_csrf_token(client):
    register(client)
    login(client)

    client.post(
        "/notes/create",
        data={
            "title": "Delete test note",
            "content": "This note must remain unchanged.",
            "category": "Testing",
        },
    )

    response = post_without_csrf(client, "/notes/delete/1")

    assert response.status_code == 400

    import app as app_module

    connection = app_module.get_db_connection()
    try:
        note = connection.execute(
            "SELECT id FROM notes WHERE id = ? AND user_id = ?",
            (1, 1),
        ).fetchone()
    finally:
        connection.close()

    assert note is not None


def test_logout_rejects_missing_csrf_token(client):
    register(client)
    login(client)

    response = post_without_csrf(client, "/logout")

    assert response.status_code == 400

    # The session should remain authenticated after the rejected request.
    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200



def test_test_database_enforces_foreign_keys(client):
    import app as app_module

    connection = app_module.get_db_connection()
    try:
        enabled = connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0]
    finally:
        connection.close()

    assert enabled == 1


def test_cannot_insert_note_for_nonexistent_user(client):
    import sqlite3
    import pytest
    import app as app_module

    connection = app_module.get_db_connection()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO notes (user_id, title, content, category)
                VALUES (?, ?, ?, ?)
                """,
                (999999, "Invalid note", "Test content", "Testing"),
            )
    finally:
        connection.close()


def test_deleting_note_also_deletes_its_comments(client):
    register(client)
    login(client)

    client.post(
        "/notes/create",
        data={
            "title": "Note with comment",
            "content": "Testing transactional deletion.",
            "category": "Testing",
        },
    )

    client.post(
        "/notes/1/comments",
        data={"content": "A comment attached to this note."},
    )

    response = client.post("/notes/delete/1")
    assert response.status_code == 200

    import app as app_module

    connection = app_module.get_db_connection()
    try:
        note_count = connection.execute(
            "SELECT COUNT(*) FROM notes WHERE id = ?",
            (1,),
        ).fetchone()[0]

        comment_count = connection.execute(
            "SELECT COUNT(*) FROM comments WHERE note_id = ?",
            (1,),
        ).fetchone()[0]
    finally:
        connection.close()

    assert note_count == 0
    assert comment_count == 0
