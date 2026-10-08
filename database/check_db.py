from db import get_db_connection


connection = get_db_connection()

users = connection.execute(
    "SELECT * FROM users"
).fetchall()

print("\n--- USERS ---")

for user in users:
    print(dict(user))


notes = connection.execute(
    "SELECT * FROM notes"
).fetchall()

print("\n--- NOTES ---")

for note in notes:
    print(dict(note))


connection.close()