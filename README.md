# Secure Student Notes Application
A Flask-based web application that allows students to register, log in, create and manage personal notes, add comments, and search their notes. This project demonstrates secure web application development and practical security testing.

## Features

- User registration and login
- Secure password hashing using Werkzeug
- Create, edit, view, and delete notes
- Add comments to notes
- Search notes
- User-specific access control
- Input validation for usernames, email addresses, passwords, and notes
- CSRF protection for form submissions
- Parameterized SQL queries to reduce SQL injection risks
- HTML escaping to help prevent cross-site scripting (XSS)
- HTTP-only session cookies and configurable secure cookie settings
- SQLite foreign-key enforcement
- Automated security and functionality tests

## Technology Stack

- Python
- Flask
- Flask-WTF
- SQLite
- HTML and CSS
- pytest

## Prerequisites

- Python 3.12 or a compatible Python version
- Git
- pip

## Installation

Clone the repository:

```bash
git clone https://github.com/rbharath2006/secure-student-notes.git
cd secure-student-notes
```

Create and activate a virtual environment.

**Windows PowerShell:**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Configuration

For local development, configure the application environment and a development secret key in PowerShell:

```powershell
$env:APP_ENV = "development"
$env:SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
$env:COOKIE_SECURE = "false"
```

Do not commit secret keys or passwords to GitHub.

## Initialize the Database

If the project database has not been initialized, run the database initialization script:

```powershell
python database/init_db.py
```

Back up any database you want to keep before reinitializing it. Check the initialization script before running it against an existing database, as initialization scripts may recreate tables or otherwise affect existing data.

## Run the Application

```powershell
python app.py
```

Open the local address printed in the terminal, typically:

http://127.0.0.1:5000

Use the application locally for development and testing.

## Run Tests

Run the complete test suite:

```powershell
python -m pytest -q
```

Check installed dependencies:

```powershell
python -m pip check
```

The security test suite covers areas such as input validation, CSRF protection, access control, SQL injection resistance, XSS escaping, and database integrity.

## Security Notes

- Passwords are hashed before storage.
- SQL queries use parameterized statements.
- Notes and comments are protected by user ownership checks.
- State-changing form submissions require CSRF protection.
- Note deletion handles related comments transactionally.
- Production deployment requires a strong secret key, HTTPS, secure cookies, and an appropriate production WSGI server.
- This project is an educational security project; testing does not guarantee that the application is free of vulnerabilities.

## Project Purpose

The purpose of this project is to understand secure coding practices, identify common web application vulnerabilities, implement appropriate mitigations, and validate those mitigations through automated testing.

## License

Add a license if you intend to distribute this project for reuse.
