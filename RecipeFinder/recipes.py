import requests

try:
    from .settings import MEALDB_BASE_URL
except ImportError:
    from settings import MEALDB_BASE_URL


def mealdb_get(endpoint, params=None):
    response = requests.get(
        f"{MEALDB_BASE_URL}{endpoint}",
        params=params or {},
        timeout=5,
    )
    response.raise_for_status()
    return response.json()


def clean_ingredient_name(ingredient_text):
    return ingredient_text.strip().lower().replace(" ", "_")


def first_ingredient(ingredients):
    return ingredients.split(",")[0].strip()


def normalize_meal(meal):
    if not meal:
        return None

    ingredients = []
    for number in range(1, 21):
        ingredient = (meal.get(f"strIngredient{number}") or "").strip()
        measure = (meal.get(f"strMeasure{number}") or "").strip()
        if ingredient:
            original = f"{measure} {ingredient}".strip()
            ingredients.append({"name": ingredient, "measure": measure, "original": original})

    instructions = meal.get("strInstructions") or "Instruction information is unavailable."
    instruction_steps = [
        step.strip() for step in instructions.replace("\r", "\n").split("\n") if step.strip()
    ]

    return {
        "id": meal.get("idMeal") or meal.get("id", ""),
        "title": meal.get("strMeal") or meal.get("title", "Untitled Recipe"),
        "image": meal.get("strMealThumb") or meal.get("image", ""),
        "category": meal.get("strCategory", ""),
        "area": meal.get("strArea", ""),
        "instructions": instruction_steps,
        "extendedIngredients": ingredients,
        "source": meal.get("strSource", ""),
        "youtube": meal.get("strYoutube", ""),
    }


def lookup_meal_details(recipe_id):
    data = mealdb_get("/lookup.php", {"i": recipe_id})
    meals = data.get("meals") or []
    return normalize_meal(meals[0]) if meals else None


def search_recipes(ingredients, category=None):
    ingredient = clean_ingredient_name(first_ingredient(ingredients))
    data = mealdb_get("/filter.php", {"i": ingredient})
    meals = data.get("meals") or []
    
    # Filter by category if provided
    if category:
        meals = [meal for meal in meals if meal.get("strCategory", "").lower() == category.lower()]
    
    return [normalize_meal(meal) for meal in meals[:12]]


def get_recipe_details(recipe_id):
    return lookup_meal_details(recipe_id)


def get_random_recipe(category=None):
    if category in ("breakfast", "dessert"):
        category_name = "Dessert" if category == "dessert" else "Breakfast"
        data = mealdb_get("/filter.php", {"c": category_name})
        meals = data.get("meals") or []
        if meals:
            return lookup_meal_details(meals[0]["idMeal"])

    data = mealdb_get("/random.php")
    recipes = data.get("meals") or []
    return normalize_meal(recipes[0]) if recipes else None


def recipe_card_nutrition(recipe):
    return "Nutrition shown in details"
