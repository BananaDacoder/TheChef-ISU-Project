import sqlite3
from datetime import datetime
from functools import wraps

import requests
from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

try:
    from .database import (
        close_database,
        create_default_folder,
        create_folder as add_folder,
        create_user,
        delete_favourite as remove_favourite,
        folder_belongs_to_user,
        get_favourite,
        get_favourite_by_recipe_id,
        get_recent_searches,
        get_user_by_id,
        get_user_by_username,
        get_user_favourites,
        get_user_folders,
        group_favourites_by_folder,
        init_database,
        mark_welcome_seen,
        save_favourite as add_favourite,
        save_search_history,
        update_favourite,
    )
    from .nutrition import get_recipe_ingredient_nutrition
    from .recipes import (
        get_random_recipe,
        get_recipe_details,
        recipe_card_nutrition,
        search_recipes,
    )
    from .settings import read_secret
except ImportError:
    from database import (
        close_database,
        create_default_folder,
        create_folder as add_folder,
        create_user,
        delete_favourite as remove_favourite,
        folder_belongs_to_user,
        get_favourite,
        get_favourite_by_recipe_id,
        get_recent_searches,
        get_user_by_id,
        get_user_by_username,
        get_user_favourites,
        get_user_folders,
        group_favourites_by_folder,
        init_database,
        mark_welcome_seen,
        save_favourite as add_favourite,
        save_search_history,
        update_favourite,
    )
    from nutrition import get_recipe_ingredient_nutrition
    from recipes import (
        get_random_recipe,
        get_recipe_details,
        recipe_card_nutrition,
        search_recipes,
    )
    from settings import read_secret


app = Flask(__name__)
app.secret_key = read_secret("SECRET_KEY", "recipe-finder-local-secret-change-me")
app.teardown_appcontext(close_database)


@app.before_request
def load_logged_in_user():
    user_id = session.get("user_id")
    g.user = get_user_by_id(user_id) if user_id else None


def login_required(route_function):
    @wraps(route_function)
    def wrapped_route(*args, **kwargs):
        if g.user is None:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return route_function(*args, **kwargs)

    return wrapped_route


def current_user_id():
    return g.user["id"]


def recent_searches():
    return get_recent_searches(current_user_id())


def folders():
    return get_user_folders(current_user_id())


def form_folder_id():
    folder_id_text = request.form.get("folder_id", "").strip()
    return int(folder_id_text) if folder_id_text.isdigit() else None


def log_user_in(user):
    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]


def save_recently_viewed(recipe):
    recent_recipes = session.get("recently_viewed", [])
    recipe_summary = {
        "id": str(recipe.get("id", "")),
        "title": recipe.get("title", "Untitled Recipe"),
        "image": recipe.get("image", ""),
    }

    recent_recipes = [item for item in recent_recipes if item.get("id") != recipe_summary["id"]]
    recent_recipes.insert(0, recipe_summary)
    session["recently_viewed"] = recent_recipes[:4]


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Please enter a username and password.", "warning")
            return render_template("register.html")

        try:
            user = create_user(username, generate_password_hash(password))
            create_default_folder(user["id"])
            log_user_in(user)
            flash("Account created. Welcome to Recipe Finder.", "success")
            return redirect(url_for("welcome"))
        except sqlite3.IntegrityError:
            flash("Username already exists.", "warning")
        except sqlite3.Error:
            flash("Unable to create account because of a database error.", "danger")

    return render_template("register.html")


@app.route("/guest")
def guest():
    guest_name = "Guest " + datetime.now().strftime("%H%M%S%f")
    user = create_user(guest_name, generate_password_hash("guest"), is_guest=True)
    create_default_folder(user["id"])
    log_user_in(user)
    flash("You are using Recipe Finder as a guest.", "success")
    return redirect(url_for("welcome"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        user = get_user_by_username(username)

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid log-in information", "danger")
            return render_template("login.html")

        log_user_in(user)
        flash("Logged in successfully.", "success")
        if not user["has_seen_welcome"]:
            return redirect(url_for("welcome"))
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/welcome")
@login_required
def welcome():
    return render_template("welcome.html")


@app.route("/finish-welcome", methods=["POST"])
@login_required
def finish_welcome():
    mark_welcome_seen(current_user_id())
    return redirect(url_for("index"))


@app.route("/")
@login_required
def index():
    return render_template(
        "index.html",
        categories=["breakfast", "lunch", "dinner", "dessert"],
        recently_viewed=session.get("recently_viewed", []),
        recent_searches=recent_searches(),
    )


@app.route("/search", methods=["POST"])
@login_required
def search():
    ingredients = request.form.get("ingredients", "").strip()
    category = request.form.get("category", "").strip()

    if not ingredients:
        flash("Please enter at least one ingredient.", "warning")
        return redirect(url_for("index"))

    try:
        recipes = search_recipes(ingredients, category or None)
    except requests.RequestException:
        return render_template("error.html", message="Unable to connect to recipe service."), 503

    if not recipes:
        flash("No results found.", "info")

    try:
        save_search_history(current_user_id(), ingredients, category, len(recipes))
    except sqlite3.Error:
        flash("Search completed, but history could not be saved.", "warning")

    return render_template(
        "results.html",
        recipes=recipes,
        ingredients=ingredients,
        category=category,
        recipe_card_nutrition=recipe_card_nutrition,
        folders=folders(),
    )


@app.route("/recipe/<recipe_id>")
@login_required
def recipe(recipe_id):
    try:
        details = get_recipe_details(recipe_id)
    except requests.RequestException:
        return render_template("error.html", message="Unable to load recipe details right now."), 503

    if not details:
        return render_template("error.html", message="Recipe not found."), 404

    save_recently_viewed(details)
    return render_template(
        "recipe.html",
        recipe=details,
        ingredient_nutrition=get_recipe_ingredient_nutrition(details),
        favourite=get_favourite_by_recipe_id(current_user_id(), recipe_id),
        folders=folders(),
    )


@app.route("/random")
@login_required
def random_recipe():
    category = request.args.get("category", "").strip()

    try:
        recipe_data = get_random_recipe(category or None)
    except requests.RequestException:
        return render_template("error.html", message="Unable to connect to recipe service."), 503

    if not recipe_data:
        flash("No random recipe was found.", "info")
        return redirect(url_for("index"))

    return redirect(url_for("recipe", recipe_id=recipe_data["id"]))


@app.route("/save-favourite", methods=["GET", "POST"])
@login_required
def save_favourite():
    if request.method == "GET":
        flash("Choose a recipe before saving it to favourites.", "warning")
        return redirect(url_for("favourites"))

    recipe_id = request.form.get("recipe_id", "").strip()
    title = request.form.get("title", "Untitled Recipe").strip()
    image_url = request.form.get("image_url", "").strip()
    folder_id = form_folder_id()

    if not recipe_id:
        flash("Unable to save this recipe.", "warning")
        return redirect(url_for("index"))

    if not folder_belongs_to_user(current_user_id(), folder_id):
        flash("Please choose one of your own folders.", "warning")
        return redirect(url_for("favourites"))

    try:
        if get_favourite_by_recipe_id(current_user_id(), recipe_id):
            flash("This recipe is already in your favourites.", "info")
        else:
            add_favourite(current_user_id(), recipe_id, title, image_url, folder_id)
            flash("Recipe saved to favourites.", "success")
    except sqlite3.Error:
        flash("Unable to save favourite because of a database error.", "danger")

    return redirect(url_for("recipe", recipe_id=recipe_id))


@app.route("/favourites")
@login_required
def favourites():
    try:
        saved_recipes = get_user_favourites(current_user_id())
        saved_folders = folders()
    except sqlite3.Error:
        return render_template("error.html", message="Unable to load favourites because of a database error."), 500

    return render_template(
        "favourites.html",
        favourites=saved_recipes,
        folders=saved_folders,
        folder_groups=group_favourites_by_folder(saved_recipes, saved_folders),
        recent_searches=recent_searches(),
    )


@app.route("/folders/create", methods=["POST"])
@login_required
def create_folder():
    folder_name = request.form.get("folder_name", "").strip()

    if not folder_name:
        flash("Please enter a folder name.", "warning")
        return redirect(url_for("favourites"))

    try:
        add_folder(current_user_id(), folder_name)
        flash("Folder created.", "success")
    except sqlite3.Error:
        flash("Unable to create folder because of a database error.", "danger")

    return redirect(url_for("favourites"))


@app.route("/favourites/<int:favourite_id>/edit", methods=["GET", "POST"])
@login_required
def edit_favourite(favourite_id):
    favourite = get_favourite(current_user_id(), favourite_id)

    if favourite is None:
        return render_template("error.html", message="Favourite not found."), 404

    if request.method == "POST":
        notes = request.form.get("notes", "").strip()
        folder_id = form_folder_id()

        if not folder_belongs_to_user(current_user_id(), folder_id):
            flash("Please choose one of your own folders.", "warning")
            return redirect(url_for("edit_favourite", favourite_id=favourite_id))

        try:
            update_favourite(favourite_id, notes, folder_id)
            flash("Favourite updated.", "success")
            return redirect(url_for("favourites"))
        except sqlite3.Error:
            flash("Unable to update notes because of a database error.", "danger")

    return render_template("edit_favourite.html", favourite=favourite, folders=folders())


@app.route("/favourites/<int:favourite_id>/delete", methods=["POST"])
@login_required
def delete_favourite(favourite_id):
    try:
        remove_favourite(current_user_id(), favourite_id)
        flash("Favourite removed.", "success")
    except sqlite3.Error:
        flash("Unable to remove favourite because of a database error.", "danger")

    return redirect(url_for("favourites"))


@app.errorhandler(404)
def page_not_found(error):
    return render_template("error.html", message="The page you are looking for does not exist."), 404


@app.errorhandler(500)
def server_error(error):
    return render_template("error.html", message="Something went wrong. Please try again."), 500


init_database()


if __name__ == "__main__":
    app.run(debug=True)
