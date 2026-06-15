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


def classify_recipe_category(raw_category):
    category_text = (raw_category or "").strip().lower()
    if "breakfast" in category_text:
        return "breakfast"
    if "dessert" in category_text or "cake" in category_text or "sweet" in category_text:
        return "dessert"
    if any(keyword in category_text for keyword in ["salad", "sandwich", "soup", "wrap", "snack", "lunch"]):
        return "lunch"
    return "dinner"


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

    raw_category = meal.get("strCategory", "")
    return {
        "id": meal.get("idMeal") or meal.get("id", ""),
        "title": meal.get("strMeal") or meal.get("title", "Untitled Recipe"),
        "image": meal.get("strMealThumb") or meal.get("image", ""),
        "category": raw_category,
        "app_category": classify_recipe_category(raw_category),
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

CATEGORY_MEAL_IDS_CACHE = {}


def get_category_meal_ids(category):
    category_key = category.lower()
    if category_key in CATEGORY_MEAL_IDS_CACHE:
        return CATEGORY_MEAL_IDS_CACHE[category_key]

    api_category = {
        "breakfast": "Breakfast",
        "dessert": "Dessert",
    }.get(category_key)

    if not api_category:
        return set()

    data = mealdb_get("/filter.php", {"c": api_category})
    ids = {meal["idMeal"] for meal in data.get("meals") or []}
    CATEGORY_MEAL_IDS_CACHE[category_key] = ids
    return ids


def filter_meals_by_category(meals, category_lower):
    if category_lower in {"breakfast", "dessert"}:
        category_ids = get_category_meal_ids(category_lower)
        filtered = [meal for meal in meals if meal["idMeal"] in category_ids]
        return [normalize_meal(meal) for meal in filtered[:12]]

    matched = []
    lookup_attempts = 0
    for meal in meals:
        if lookup_attempts >= 30:
            break
        lookup_attempts += 1

        details = lookup_meal_details(meal["idMeal"])
        if details and details.get("app_category") == category_lower:
            matched.append(details)
            if len(matched) >= 12:
                break

    return matched


def search_recipes(ingredients, category=None):
    # Parse all ingredients from comma-separated string
    ingredient_list = [ing.strip() for ing in ingredients.split(",")]
    
    # Collect all recipes from all ingredients
    all_meals = {}
    for ingredient in ingredient_list:
        cleaned_ingredient = clean_ingredient_name(ingredient)
        data = mealdb_get("/filter.php", {"i": cleaned_ingredient})
        for meal in data.get("meals") or []:
            all_meals[meal["idMeal"]] = meal
    
    meals = list(all_meals.values())

    if not category:
        return [normalize_meal(meal) for meal in meals[:12]]

    category_lower = category.lower()
    results = filter_meals_by_category(meals, category_lower)
    if results:
        return results

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
