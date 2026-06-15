import sqlite3
from datetime import datetime

from flask import g

try:
    from .settings import DATABASE_PATH
except ImportError:
    from settings import DATABASE_PATH


def get_database():
    """Open one database connection for the current page request."""
    if "database" not in g:
        g.database = sqlite3.connect(DATABASE_PATH)
        g.database.row_factory = sqlite3.Row
    return g.database


def close_database(error=None):
    database = g.pop("database", None)
    if database is not None:
        database.close()


def add_column_if_missing(database, table_name, column_name, column_sql):
    columns = [row[1] for row in database.execute(f"PRAGMA table_info({table_name})")]
    if column_name not in columns:
        database.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")


def init_database():
    """Create or update the app database."""
    with sqlite3.connect(DATABASE_PATH) as database:
        database.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                date_joined TEXT NOT NULL,
                has_seen_welcome INTEGER DEFAULT 0,
                is_guest INTEGER DEFAULT 0
            )
            """
        )
        database.execute(
            """
            CREATE TABLE IF NOT EXISTS folders (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                date_created TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            """
        )
        database.execute(
            """
            CREATE TABLE IF NOT EXISTS favourites (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                recipe_id TEXT,
                title TEXT,
                image_url TEXT,
                notes TEXT,
                folder_id INTEGER,
                date_saved TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (folder_id) REFERENCES folders (id)
            )
            """
        )
        database.execute(
            """
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                ingredients TEXT NOT NULL,
                category TEXT,
                result_count INTEGER,
                searched_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            """
        )

        add_column_if_missing(database, "users", "has_seen_welcome", "has_seen_welcome INTEGER DEFAULT 0")
        add_column_if_missing(database, "users", "is_guest", "is_guest INTEGER DEFAULT 0")
        add_column_if_missing(database, "favourites", "user_id", "user_id INTEGER")
        add_column_if_missing(database, "favourites", "folder_id", "folder_id INTEGER")
        database.commit()


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def create_user(username, password_hash, is_guest=False):
    database = get_database()
    database.execute(
        """
        INSERT INTO users
        (username, password_hash, date_joined, has_seen_welcome, is_guest)
        VALUES (?, ?, ?, ?, ?)
        """,
        (username, password_hash, now_text(), 0, 1 if is_guest else 0),
    )
    database.commit()
    return database.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def create_default_folder(user_id):
    create_folder(user_id, "Recipes to Try")


def create_folder(user_id, folder_name):
    database = get_database()
    database.execute(
        """
        INSERT INTO folders (user_id, name, date_created)
        VALUES (?, ?, ?)
        """,
        (user_id, folder_name, now_text()),
    )
    database.commit()


def get_user_by_id(user_id):
    return get_database().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_user_by_username(username):
    return get_database().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def mark_welcome_seen(user_id):
    database = get_database()
    database.execute("UPDATE users SET has_seen_welcome = 1 WHERE id = ?", (user_id,))
    database.commit()


def get_user_folders(user_id):
    return get_database().execute(
        """
        SELECT * FROM folders
        WHERE user_id = ?
        ORDER BY name
        """,
        (user_id,),
    ).fetchall()


def folder_belongs_to_user(user_id, folder_id):
    if not folder_id:
        return True

    folder = get_database().execute(
        "SELECT id FROM folders WHERE id = ? AND user_id = ?",
        (folder_id, user_id),
    ).fetchone()
    return folder is not None


def save_search_history(user_id, ingredients, category, result_count):
    database = get_database()
    database.execute(
        """
        INSERT INTO search_history
        (user_id, ingredients, category, result_count, searched_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, ingredients, category, result_count, now_text()),
    )
    database.commit()


def get_recent_searches(user_id, limit=6):
    if user_id is None:
        return []

    return get_database().execute(
        """
        SELECT * FROM search_history
        WHERE user_id = ?
        ORDER BY searched_at DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()


def get_favourite_by_recipe_id(user_id, recipe_id):
    return get_database().execute(
        "SELECT * FROM favourites WHERE recipe_id = ? AND user_id = ?",
        (str(recipe_id), user_id),
    ).fetchone()


def save_favourite(user_id, recipe_id, title, image_url, folder_id):
    database = get_database()
    database.execute(
        """
        INSERT INTO favourites
        (user_id, recipe_id, title, image_url, notes, folder_id, date_saved)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, recipe_id, title, image_url, "", folder_id, now_text()),
    )
    database.commit()


def get_user_favourites(user_id):
    return get_database().execute(
        """
        SELECT * FROM favourites
        WHERE user_id = ?
        ORDER BY date_saved DESC
        """,
        (user_id,),
    ).fetchall()


def get_favourite(user_id, favourite_id):
    return get_database().execute(
        "SELECT * FROM favourites WHERE id = ? AND user_id = ?",
        (favourite_id, user_id),
    ).fetchone()


def update_favourite(favourite_id, notes, folder_id):
    database = get_database()
    database.execute(
        "UPDATE favourites SET notes = ?, folder_id = ? WHERE id = ?",
        (notes, folder_id, favourite_id),
    )
    database.commit()


def delete_favourite(user_id, favourite_id):
    database = get_database()
    database.execute(
        "DELETE FROM favourites WHERE id = ? AND user_id = ?",
        (favourite_id, user_id),
    )
    database.commit()


def group_favourites_by_folder(favourites, folders):
    folder_groups = []

    for folder in folders:
        folder_recipes = []
        for favourite in favourites:
            if favourite["folder_id"] == folder["id"]:
                folder_recipes.append(favourite)

        folder_groups.append(
            {"id": folder["id"], "name": folder["name"], "favourites": folder_recipes}
        )

    no_folder_recipes = []
    for favourite in favourites:
        if favourite["folder_id"] is None:
            no_folder_recipes.append(favourite)

    if no_folder_recipes:
        folder_groups.append(
            {"id": None, "name": "No Folder", "favourites": no_folder_recipes}
        )

    return folder_groups
