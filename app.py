from flask import Flask, render_template, request, session
from database.db import get_db_connection

app = Flask(__name__)

# Development secret key
# We will move this to an environment variable in the secure version.
app.secret_key = "student-notes-development-key"


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

        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        connection = get_db_connection()

        try:

            connection.execute(
                """
                INSERT INTO users (username, email, password)
                VALUES (?, ?, ?)
                """,
                (username, email, password)
            )

            connection.commit()

        except Exception as error:

            connection.close()

            return f"""
            <h1>Registration Failed</h1>

            <p>{error}</p>

            <a href="/register">Try Again</a>
            """

        connection.close()

        return """
        <h1>Registration Successful!</h1>

        <p>Your account has been created.</p>

        <a href="/login">Login Now</a>
        """

    return render_template("register.html")


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        connection = get_db_connection()

        user = connection.execute(
            """
            SELECT *
            FROM users
            WHERE username = ? AND password = ?
            """,
            (username, password)
        ).fetchone()

        connection.close()

        if user:

            # Store authenticated user's information
            # in the Flask session.
            session["user_id"] = user["id"]
            session["username"] = user["username"]

            return render_template(
                "dashboard.html",
                username=user["username"]
            )

        return """
        <h1>Login Failed</h1>

        <p>Invalid username or password.</p>

        <a href="/login">Try Again</a>
        """

    return render_template("login.html")


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
def dashboard():

    # User must be logged in
    if "user_id" not in session:

        return """
        <h1>Access Denied</h1>

        <p>You must login first.</p>

        <a href="/login">Login</a>
        """

    connection = get_db_connection()

    notes = connection.execute(
        """
        SELECT *
        FROM notes
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (session["user_id"],)
    ).fetchall()

    connection.close()

    return render_template(
        "dashboard.html",
        username=session["username"],
        notes=notes
    )

# ============================================================
# CREATE NOTE
# ============================================================

@app.route("/notes/create", methods=["GET", "POST"])
def create_note():

    # User must be logged in
    if "user_id" not in session:

        return """
        <h1>Access Denied</h1>

        <p>You must login first.</p>

        <a href="/login">Login</a>
        """

    if request.method == "POST":

        title = request.form["title"]
        content = request.form["content"]
        category = request.form["category"]

        connection = get_db_connection()

        connection.execute(
            """
            INSERT INTO notes
            (user_id, title, content, category)
            VALUES (?, ?, ?, ?)
            """,
            (
                session["user_id"],
                title,
                content,
                category
            )
        )

        connection.commit()
        connection.close()

        return """
        <h1>Note Created Successfully!</h1>

        <p>Your note has been saved.</p>

        <a href="/dashboard">Go to Dashboard</a>
        """

    return render_template("create_note.html")


# ============================================================
# EDIT NOTE
# ============================================================

@app.route("/notes/edit/<int:note_id>", methods=["GET", "POST"])
def edit_note(note_id):

    # User must be logged in
    if "user_id" not in session:

        return """
        <h1>Access Denied</h1>

        <p>You must login first.</p>

        <a href="/login">Login</a>
        """

    connection = get_db_connection()

    # Retrieve only the current user's note
    note = connection.execute(
        """
        SELECT *
        FROM notes
        WHERE id = ? AND user_id = ?
        """,
        (note_id, session["user_id"])
    ).fetchone()

    if note is None:

        connection.close()

        return """
        <h1>Note Not Found</h1>

        <p>
            The note does not exist or does not belong to you.
        </p>

        <a href="/dashboard">Back to Dashboard</a>
        """

    if request.method == "POST":

        title = request.form["title"]
        category = request.form["category"]
        content = request.form["content"]

        connection.execute(
            """
            UPDATE notes
            SET title = ?,
                category = ?,
                content = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                title,
                category,
                content,
                note_id,
                session["user_id"]
            )
        )

        connection.commit()
        connection.close()

        return """
        <h1>Note Updated Successfully!</h1>

        <p>Your note has been updated.</p>

        <a href="/dashboard">
            Back to Dashboard
        </a>
        """

    connection.close()

    return render_template(
        "edit_note.html",
        note=note
    )


# ============================================================
# DELETE NOTE
# ============================================================

@app.route("/notes/delete/<int:note_id>")
def delete_note(note_id):

    # User must be logged in
    if "user_id" not in session:

        return """
        <h1>Access Denied</h1>

        <p>You must login first.</p>

        <a href="/login">Login</a>
        """

    connection = get_db_connection()

    connection.execute(
        """
        DELETE FROM notes
        WHERE id = ? AND user_id = ?
        """,
        (
            note_id,
            session["user_id"]
        )
    )

    connection.commit()
    connection.close()

    return """
    <h1>Note Deleted</h1>

    <p>The note has been deleted successfully.</p>

    <a href="/dashboard">
        Back to Dashboard
    </a>
    """

# ============================================================
# COMMENTS
# ============================================================

@app.route("/notes/<int:note_id>/comments", methods=["GET", "POST"])
def comments(note_id):

    # User must be logged in
    if "user_id" not in session:

        return """
        <h1>Access Denied</h1>

        <p>You must login first.</p>

        <a href="/login">Login</a>
        """

    connection = get_db_connection()

    # Get the note
    note = connection.execute(
        """
        SELECT *
        FROM notes
        WHERE id = ?
        """,
        (note_id,)
    ).fetchone()

    if note is None:

        connection.close()

        return """
        <h1>Note Not Found</h1>

        <a href="/dashboard">
            Back to Dashboard
        </a>
        """

    # Add comment
    if request.method == "POST":

        content = request.form["content"]

        connection.execute(
            """
            INSERT INTO comments
            (note_id, user_id, content)
            VALUES (?, ?, ?)
            """,
            (
                note_id,
                session["user_id"],
                content
            )
        )

        connection.commit()

    # Retrieve comments
    comments = connection.execute(
        """
        SELECT
            comments.id,
            comments.content,
            comments.created_at,
            users.username
        FROM comments
        JOIN users
            ON comments.user_id = users.id
        WHERE comments.note_id = ?
        ORDER BY comments.created_at DESC
        """,
        (note_id,)
    ).fetchall()

    connection.close()

    return render_template(
        "comments.html",
        note=note,
        comments=comments
    )



# ============================================================
# PROFILE
# ============================================================

@app.route("/profile", methods=["GET", "POST"])
def profile():

    # User must be logged in
    if "user_id" not in session:

        return """
        <h1>Access Denied</h1>

        <p>You must login first.</p>

        <a href="/login">Login</a>
        """

    connection = get_db_connection()

    # Get current user
    user = connection.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (session["user_id"],)
    ).fetchone()

    if request.method == "POST":

        new_email = request.form["email"]

        connection.execute(
            """
            UPDATE users
            SET email = ?
            WHERE id = ?
            """,
            (
                new_email,
                session["user_id"]
            )
        )

        connection.commit()

        # Get updated user information
        user = connection.execute(
            """
            SELECT *
            FROM users
            WHERE id = ?
            """,
            (session["user_id"],)
        ).fetchone()

        connection.close()

        return render_template(
            "profile.html",
            user=user
        )

    connection.close()

    return render_template(
        "profile.html",
        user=user
    )




# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    # Remove all session information.
    session.clear()

    return """
    <h1>Logged Out</h1>

    <p>You have been successfully logged out.</p>

    <a href="/login">Login Again</a>

    <br><br>

    <a href="/">Home</a>
    """
# ============================================================
# SEARCH NOTES
# ============================================================

@app.route("/search")
def search_notes():

    # User must be logged in
    if "user_id" not in session:

        return """
        <h1>Access Denied</h1>

        <p>You must login first.</p>

        <a href="/login">Login</a>
        """

    query = request.args.get("q", "").strip()

    notes = []

    if query:

        connection = get_db_connection()

        notes = connection.execute(
            """
            SELECT *
            FROM notes
            WHERE user_id = ?
            AND (
                title LIKE ?
                OR content LIKE ?
                OR category LIKE ?
            )
            ORDER BY created_at DESC
            """,
            (
                session["user_id"],
                f"%{query}%",
                f"%{query}%",
                f"%{query}%"
            )
        ).fetchall()

        connection.close()

    return render_template(
        "search.html",
        notes=notes,
        query=query
    )

# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":
    app.run(debug=True)