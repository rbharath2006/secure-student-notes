# Secure Student Notes

A secure student notes web application built using Flask and SQLite. Students can register, log in, and create, organize, search, edit, and delete their personal notes.

## Live Website

**https://rbharath06.pythonanywhere.com**

## Features

- User registration and login
- Create, edit, search, and delete notes
- Comments on notes
- Password hashing
- CSRF protection
- Parameterized SQL queries
- Authentication and note-ownership checks
- Security headers and secure session cookies
- SQLite database backup utility

## Technologies Used

- Python 3.12
- Flask
- SQLite
- HTML, CSS, JavaScript
- Pytest
- Git and GitHub
- PythonAnywhere

## Installation and Setup

### 1. Clone the repository

```bash
git clone -b v2-secure https://github.com/rbharath2006/secure-student-notes.git
cd secure-student-notes
```

### 2. Create a virtual environment

**Windows PowerShell**

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```

**Linux/macOS**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Initialize the database

```bash
python database/init_db.py
```

### 5. Run the application

```bash
python app.py
```

Open the local address displayed in the terminal.

## Run Tests

Execute the automated test suite:

```bash
pytest -q
```

The latest recorded test run completed with **50 passing tests**.

## Database Backup

Create a backup of the SQLite database:

```bash
python backup_database.py
```

Keep database backups private and store them securely.

## Security

The application includes password hashing, CSRF protection, parameterized SQL queries, authorization checks, security headers, and secure session-cookie settings.

For production deployments, use a strong, unique `SECRET_KEY`, enable production mode, and serve the application over HTTPS. Never commit secrets or production database files to GitHub.

## Deployment

The application is deployed on PythonAnywhere:

**https://rbharath06.pythonanywhere.com**

The production database is separate from the local development database.
