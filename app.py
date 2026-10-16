import os
import re
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, session, redirect, url_for
from flask_wtf.csrf import CSRFProtect
from database.db import get_db_connection



app = Flask(__name__)

app_env = os.environ.get("APP_ENV", "development").lower()
secret_key = os.environ.get("SECRET_KEY")

if not secret_key:
    if app_env == "production":
        raise RuntimeError(
            "SECRET_KEY must be configured in production."
        )
    secret_key = "local-development-key-change-before-deployment"

app.config["SECRET_KEY"] = secret_key
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Secure cookies by default in production; local HTTP development
# can use non-secure cookies.
secure_cookie_default = "true" if app_env == "production" else "false"
app.config["SESSION_COOKIE_SECURE"] = (
    os.environ.get("COOKIE_SECURE", secure_cookie_default).lower()
    == "true"
)

csrf = CSRFProtect(app)



def validate_email(email):
    """Validate an email address before saving it."""
    if len(email) > 254 or not re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+", email
    ):
        return "Please enter a valid email address."

    return None




def validate_registration(username, email, password):
    """Validate registration details before saving them."""

    # Username: 3–30 characters, letters, numbers, underscores only
    if not re.fullmatch(r"[A-Za-z0-9_]{3,30}", username):
        return (
            "Username must be 3–30 characters and contain only "
            "letters, numbers, and underscores."
        )

    # Email: basic format validation and maximum length
    if len(email) > 254 or not re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+", email
    ):
        return "Please enter a valid email address."

    # Password: minimum 12 characters, maximum 128 characters
    if not 12 <= len(password) <= 128:
        return "Password must be between 12 and 128 characters."

    return None


def validate_note(title, content, category):
    """Validate note fields before saving them."""
    if not title:
        return "A note title is required."
    if len(title) > 150:
        return "The title must be 150 characters or fewer."

    if not content:
        return "Note content is required."
    if len(content) > 10000:
        return "Note content must be 10,000 characters or fewer."

    if len(category) > 50:
        return "The category must be 50 characters or fewer."

    return None


def render_status(title, message, action_text="Go to Dashboard", action_endpoint="dashboard",
                  layout="app", status_code=200):
    """Render a consistent styled status page instead of returning raw HTML."""
    template = "auth_status.html" if layout == "auth" else "status.html"
    action_url = url_for(action_endpoint) if action_endpoint else None
    return render_template(
        template,
        page_title=title,
        message=message,
        action_text=action_text,
        action_url=action_url,
        username=session.get("username"),
    ), status_code


def login_required_status():
    return render_status(
        "Sign in required",
        "Please sign in to access this part of your workspace.",
        "Sign in",
        "login",
        layout="auth",
        status_code=401,
    )


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():
    return render_template("index.html")



# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        # Check for empty fields
        if not username or not email or not password:
            return render_status(
                "Registration incomplete",
                "Please fill in all required fields.",
                "Try again",
                "register",
                layout="auth",
                status_code=400,
            )

        # Validate input before accessing the database
        validation_error = validate_registration(
            username, email, password
        )

        if validation_error:
            return render_status(
                "Invalid registration details",
                validation_error,
                "Try again",
                "register",
                layout="auth",
                status_code=400,
            )

        connection = get_db_connection()

        try:
            connection.execute(
                """
                INSERT INTO users (username, email, password)
                VALUES (?, ?, ?)
                """,
                (
                    username,
                    email,
                    generate_password_hash(password),
                ),
            )
            connection.commit()

        except sqlite3.IntegrityError:
            # Do not expose database details to the browser.
            return render_status(
                "Registration could not be completed",
                (
                    "That username or email may already be registered. "
                    "Please try again with different details."
                ),
                "Try again",
                "register",
                layout="auth",
                status_code=400,
            )

        finally:
            connection.close()

        return render_status(
            "Registration successful",
            "Your account has been created. You can now sign in.",
            "Sign in",
            "login",
            layout="auth",
        )

    return render_template("register.html")



# ============================================================
# LOGIN
# ============================================================


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        connection = get_db_connection()
        authenticated_user = None

        try:
            user = connection.execute(
                """
                SELECT *
                FROM users
                WHERE username = ?
                """,
                (username,),
            ).fetchone()

            if user:
                stored_password = user["password"]
                password_valid = False

                # First, check passwords stored as secure hashes.
                try:
                    password_valid = check_password_hash(
                        stored_password, password
                    )
                except (ValueError, TypeError):
                    password_valid = False

                # Upgrade a legacy plaintext password after a successful login.
                if not password_valid and stored_password == password:
                    password_valid = True

                    upgraded_hash = generate_password_hash(password)
                    connection.execute(
                        "UPDATE users SET password = ? WHERE id = ?",
                        (upgraded_hash, user["id"]),
                    )
                    connection.commit()

                if password_valid:
                    authenticated_user = {
                        "id": user["id"],
                        "username": user["username"],
                    }

        finally:
            connection.close()

        if authenticated_user:
            session.clear()
            session["user_id"] = authenticated_user["id"]
            session["username"] = authenticated_user["username"]
            return redirect(url_for("dashboard"))

        return render_status(
            "Sign-in failed",
            "The username or password was incorrect. Please try again.",
            "Try again",
            "login",
            layout="auth",
            status_code=401,
        )

    return render_template("login.html")


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return login_required_status()

    connection = get_db_connection()
    try:
        notes = connection.execute(
            """
            SELECT *
            FROM notes
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (session["user_id"],),
        ).fetchall()
    finally:
        connection.close()

    return render_template(
        "dashboard.html",
        username=session.get("username"),
        notes=notes,
    )



# ============================================================
# CREATE NOTE
# ============================================================

@app.route("/notes/create", methods=["GET", "POST"])
def create_note():
    if "user_id" not in session:
        return login_required_status()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        category = request.form.get("category", "").strip()

        # Validate note fields
        validation_error = validate_note(title, content, category)

        if validation_error:
            return render_status(
                "Note not created",
                validation_error,
                "Try again",
                "create_note",
                status_code=400,
            )

        # Save the note securely
        connection = get_db_connection()
        try:
            connection.execute(
                """
                INSERT INTO notes (user_id, title, content, category)
                VALUES (?, ?, ?, ?)
                """,
                (session["user_id"], title, content, category),
            )
            connection.commit()
        finally:
            connection.close()

        return render_status(
            "Note created successfully",
            "Your note has been saved to your workspace.",
            "Go to Dashboard",
            "dashboard",
        )

    return render_template(
        "create_note.html",
        username=session.get("username"),
    )


# ============================================================
# EDIT NOTE
# ============================================================

@app.route("/notes/edit/<int:note_id>", methods=["GET", "POST"])
def edit_note(note_id):
    if "user_id" not in session:
        return login_required_status()

    connection = get_db_connection()
    try:
        note = connection.execute(
            """
            SELECT *
            FROM notes
            WHERE id = ? AND user_id = ?
            """,
            (note_id, session["user_id"]),
        ).fetchone()

        if note is None:
            return render_status(
                "Note not found",
                "The note does not exist or does not belong to your account.",
                "Back to Dashboard",
                "dashboard",
                status_code=404,
            )

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            category = request.form.get("category", "").strip()
            content = request.form.get("content", "").strip()

            validation_error = validate_note(title, content, category)

            if validation_error:
                return render_status(
                    "Note not updated",
                    validation_error,
                    "Back to Dashboard",
                    "dashboard",
                    status_code=400,
                )

            connection.execute(
                """
                UPDATE notes
                SET title = ?, category = ?, content = ?
                WHERE id = ? AND user_id = ?
                """,
                (title, category, content, note_id, session["user_id"]),
            )
            connection.commit()
            return render_status(
                "Note updated successfully",
                "Your changes have been saved.",
                "Back to Dashboard",
                "dashboard",
            )
    finally:
        connection.close()

    return render_template(
        "edit_note.html",
        note=note,
        username=session.get("username"),
    )


# ============================================================
# DELETE NOTE — POST-only, CSRF-protected, and owner-scoped.
# ============================================================


@app.route("/notes/delete/<int:note_id>", methods=["POST"])
def delete_note(note_id):
    if "user_id" not in session:
        return login_required_status()

    connection = get_db_connection()

    try:
        connection.execute("BEGIN")

        # Verify ownership before deleting anything.
        note = connection.execute(
            "SELECT id FROM notes WHERE id = ? AND user_id = ?",
            (note_id, session["user_id"]),
        ).fetchone()

        if note is None:
            connection.rollback()
            deleted = False
        else:
            # Remove dependent comments first because cascading
            # deletion is not configured in the current schema.
            connection.execute(
                "DELETE FROM comments WHERE note_id = ?",
                (note_id,),
            )

            cursor = connection.execute(
                "DELETE FROM notes WHERE id = ? AND user_id = ?",
                (note_id, session["user_id"]),
            )

            deleted = cursor.rowcount > 0

            if deleted:
                connection.commit()
            else:
                connection.rollback()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    if not deleted:
        return render_status(
            "Note not found",
            "The note does not exist or does not belong to your account.",
            "Back to Dashboard",
            "dashboard",
            status_code=404,
        )

    return render_status(
        "Note deleted",
        "Your note has been deleted successfully.",
        "Back to Dashboard",
        "dashboard",
    )



# ============================================================
# COMMENTS
# ============================================================


@app.route("/notes/<int:note_id>/comments", methods=["GET", "POST"])
def comments(note_id):
    if "user_id" not in session:
        return login_required_status()

    connection = get_db_connection()
    try:
        # Only retrieve notes owned by the current user.
        note = connection.execute(
            "SELECT * FROM notes WHERE id = ? AND user_id = ?",
            (note_id, session["user_id"]),
        ).fetchone()

        # Use the same response for nonexistent and unauthorized notes.
        if note is None:
            return render_status(
                "Note not found",
                "The requested note could not be found.",
                "Back to Dashboard",
                "dashboard",
                status_code=404,
            )

        if request.method == "POST":
            content = request.form.get("content", "").strip()

            if not content:
                return render_status(
                    "Comment not added",
                    "Please enter a comment before submitting.",
                    "Back to Comments",
                    "comments",
                    status_code=400,
                )

            connection.execute(
                """
                INSERT INTO comments (note_id, user_id, content)
                VALUES (?, ?, ?)
                """,
                (note_id, session["user_id"], content),
            )
            connection.commit()

        # This query runs only after note ownership has been verified.
        comments_rows = connection.execute(
            """
            SELECT comments.id, comments.content,
                   comments.created_at, users.username
            FROM comments
            JOIN users ON comments.user_id = users.id
            WHERE comments.note_id = ?
            ORDER BY comments.created_at DESC
            """,
            (note_id,),
        ).fetchall()
    finally:
        connection.close()

    return render_template(
        "comments.html",
        note=note,
        comments=comments_rows,
        username=session.get("username"),
    )




# ============================================================
# PROFILE
# ============================================================

@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        return login_required_status()

    connection = get_db_connection()
    try:
        if request.method == "POST":
            new_email = request.form.get("email", "").strip()
            validation_error = validate_email(new_email)

            if validation_error:
                user = connection.execute(
                    "SELECT * FROM users WHERE id = ?",
                    (session["user_id"],),
                ).fetchone()

                return render_template(
                    "profile.html",
                    user=user,
                    username=session.get("username"),
                    error_message=validation_error,
                )

            connection.execute(
                "UPDATE users SET email = ? WHERE id = ?",
                (new_email, session["user_id"]),
            )
            connection.commit()

        user = connection.execute(
            "SELECT * FROM users WHERE id = ?",
            (session["user_id"],),
        ).fetchone()
    finally:
        connection.close()

    return render_template(
        "profile.html",
        user=user,
        username=session.get("username"),
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return render_status(
        "You are signed out",
        "You have been successfully logged out of Secure Notes.",
        "Sign in again",
        "login",
        layout="auth",
    )


# ============================================================
# SEARCH NOTES
# ============================================================

@app.route("/search")
def search_notes():
    if "user_id" not in session:
        return login_required_status()

    query = request.args.get("q", "").strip()
    notes = []

    if query:
        connection = get_db_connection()
        try:
            notes = connection.execute(
                """
                SELECT *
                FROM notes
                WHERE user_id = ?
                  AND (title LIKE ? OR content LIKE ? OR category LIKE ?)
                ORDER BY created_at DESC
                """,
                (
                    session["user_id"],
                    f"%{query}%",
                    f"%{query}%",
                    f"%{query}%",
                ),
            ).fetchall()
        finally:
            connection.close()

    return render_template(
        "search.html",
        notes=notes,
        query=query,
        username=session.get("username"),
    )


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":
    app.run(debug=False)
