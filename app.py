from flask import Flask, render_template, request, session, redirect, url_for
from database.db import get_db_connection

app = Flask(__name__)

# Development-only key. Keep this branch local; move the key to an environment
# variable and configure secure cookie settings in the secure V2 phase.
app.secret_key = "student-notes-development-key"


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

        if not username or not email or not password:
            return render_status(
                "Registration incomplete",
                "Please fill in all required fields.",
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
                (username, email, password),
            )
            connection.commit()
        except Exception:
            # Do not expose database details in the browser.
            connection.close()
            return render_status(
                "Registration could not be completed",
                "That username or email may already be registered. Please try again with different details.",
                "Try again",
                "register",
                layout="auth",
                status_code=400,
            )
        finally:
            # close() is safe even if the exception branch already closed it.
            try:
                connection.close()
            except Exception:
                pass

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
        try:
            user = connection.execute(
                """
                SELECT *
                FROM users
                WHERE username = ? AND password = ?
                """,
                (username, password),
            ).fetchone()
        finally:
            connection.close()

        if user:
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
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

        if not title or not content:
            return render_status(
                "Note not created",
                "A title and note content are required.",
                "Try again",
                "create_note",
                status_code=400,
            )

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

    return render_template("create_note.html", username=session.get("username"))


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

            if not title or not content:
                return render_status(
                    "Note not updated",
                    "A title and note content are required.",
                    "Back to Edit Note",
                    "edit_note",
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
# DELETE NOTE
# NOTE: This remains a GET route in this lab baseline. It should be
# changed to POST with CSRF protection during the secure V2 phase.
# ============================================================

@app.route("/notes/delete/<int:note_id>")
def delete_note(note_id):
    if "user_id" not in session:
        return login_required_status()

    connection = get_db_connection()
    try:
        connection.execute(
            "DELETE FROM notes WHERE id = ? AND user_id = ?",
            (note_id, session["user_id"]),
        )
        connection.commit()
    finally:
        connection.close()

    return render_status(
        "Note deletion complete",
        "The selected note has been deleted if it belonged to your account.",
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
        note = connection.execute(
            "SELECT * FROM notes WHERE id = ?",
            (note_id,),
        ).fetchone()

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

        comments_rows = connection.execute(
            """
            SELECT comments.id, comments.content, comments.created_at, users.username
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
            if not new_email:
                user = connection.execute(
                    "SELECT * FROM users WHERE id = ?",
                    (session["user_id"],),
                ).fetchone()
                return render_template(
                    "profile.html",
                    user=user,
                    username=session.get("username"),
                    error_message="Email address cannot be empty.",
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

@app.route("/logout")
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
    # Debug mode is kept for this local learning branch only.
    app.run(debug=True)
