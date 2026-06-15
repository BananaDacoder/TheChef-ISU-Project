import json
import re

import requests

try:
    from .settings import FDC_BASE_URL, OPENAI_BASE_URL, read_secret
except ImportError:
    from settings import FDC_BASE_URL, OPENAI_BASE_URL, read_secret


NUTRITION_CACHE = {}
COMMON_NUTRITION = {
    "apple": {"calories": "52 kcal", "protein": "0.3 g", "carbohydrates": "13.8 g", "fat": "0.2 g"},
    "banana": {"calories": "89 kcal", "protein": "1.1 g", "carbohydrates": "22.8 g", "fat": "0.3 g"},
    "beef": {"calories": "250 kcal", "protein": "26.0 g", "carbohydrates": "0.0 g", "fat": "15.0 g"},
    "bell pepper": {"calories": "31 kcal", "protein": "1.0 g", "carbohydrates": "6.0 g", "fat": "0.3 g"},
    "bread": {"calories": "265 kcal", "protein": "9.0 g", "carbohydrates": "49.0 g", "fat": "3.2 g"},
    "broccoli": {"calories": "34 kcal", "protein": "2.8 g", "carbohydrates": "6.6 g", "fat": "0.4 g"},
    "butter": {"calories": "717 kcal", "protein": "0.9 g", "carbohydrates": "0.1 g", "fat": "81.1 g"},
    "carrot": {"calories": "41 kcal", "protein": "0.9 g", "carbohydrates": "9.6 g", "fat": "0.2 g"},
    "cheese": {"calories": "402 kcal", "protein": "25.0 g", "carbohydrates": "1.3 g", "fat": "33.0 g"},
    "chicken": {"calories": "165 kcal", "protein": "31.0 g", "carbohydrates": "0.0 g", "fat": "3.6 g"},
    "cream": {"calories": "340 kcal", "protein": "2.1 g", "carbohydrates": "2.8 g", "fat": "36.0 g"},
    "egg": {"calories": "143 kcal", "protein": "12.6 g", "carbohydrates": "0.7 g", "fat": "9.5 g"},
    "flour": {"calories": "364 kcal", "protein": "10.3 g", "carbohydrates": "76.3 g", "fat": "1.0 g"},
    "garlic": {"calories": "149 kcal", "protein": "6.4 g", "carbohydrates": "33.1 g", "fat": "0.5 g"},
    "ginger": {"calories": "80 kcal", "protein": "1.8 g", "carbohydrates": "17.8 g", "fat": "0.8 g"},
    "honey": {"calories": "304 kcal", "protein": "0.3 g", "carbohydrates": "82.4 g", "fat": "0.0 g"},
    "lemon": {"calories": "29 kcal", "protein": "1.1 g", "carbohydrates": "9.3 g", "fat": "0.3 g"},
    "lettuce": {"calories": "15 kcal", "protein": "1.4 g", "carbohydrates": "2.9 g", "fat": "0.2 g"},
    "lime": {"calories": "30 kcal", "protein": "0.7 g", "carbohydrates": "10.5 g", "fat": "0.2 g"},
    "milk": {"calories": "61 kcal", "protein": "3.2 g", "carbohydrates": "4.8 g", "fat": "3.3 g"},
    "mushroom": {"calories": "22 kcal", "protein": "3.1 g", "carbohydrates": "3.3 g", "fat": "0.3 g"},
    "oil": {"calories": "884 kcal", "protein": "0.0 g", "carbohydrates": "0.0 g", "fat": "100.0 g"},
    "olive oil": {"calories": "884 kcal", "protein": "0.0 g", "carbohydrates": "0.0 g", "fat": "100.0 g"},
    "onion": {"calories": "40 kcal", "protein": "1.1 g", "carbohydrates": "9.3 g", "fat": "0.1 g"},
    "orange": {"calories": "47 kcal", "protein": "0.9 g", "carbohydrates": "11.8 g", "fat": "0.1 g"},
    "pasta": {"calories": "131 kcal", "protein": "5.0 g", "carbohydrates": "25.0 g", "fat": "1.1 g"},
    "pepper": {"calories": "20 kcal", "protein": "0.9 g", "carbohydrates": "4.6 g", "fat": "0.2 g"},
    "pork": {"calories": "242 kcal", "protein": "27.0 g", "carbohydrates": "0.0 g", "fat": "14.0 g"},
    "potato": {"calories": "77 kcal", "protein": "2.0 g", "carbohydrates": "17.5 g", "fat": "0.1 g"},
    "rice": {"calories": "130 kcal", "protein": "2.7 g", "carbohydrates": "28.0 g", "fat": "0.3 g"},
    "salmon": {"calories": "208 kcal", "protein": "20.0 g", "carbohydrates": "0.0 g", "fat": "13.0 g"},
    "salt": {"calories": "0 kcal", "protein": "0.0 g", "carbohydrates": "0.0 g", "fat": "0.0 g"},
    "shrimp": {"calories": "99 kcal", "protein": "24.0 g", "carbohydrates": "0.2 g", "fat": "0.3 g"},
    "soy sauce": {"calories": "53 kcal", "protein": "8.1 g", "carbohydrates": "4.9 g", "fat": "0.6 g"},
    "sugar": {"calories": "387 kcal", "protein": "0.0 g", "carbohydrates": "100.0 g", "fat": "0.0 g"},
    "thyme": {"calories": "101 kcal", "protein": "5.6 g", "carbohydrates": "24.5 g", "fat": "1.7 g"},
    "tomato": {"calories": "18 kcal", "protein": "0.9 g", "carbohydrates": "3.9 g", "fat": "0.2 g"},
    "turkey": {"calories": "189 kcal", "protein": "29.0 g", "carbohydrates": "0.0 g", "fat": "7.0 g"},
    "yogurt": {"calories": "61 kcal", "protein": "3.5 g", "carbohydrates": "4.7 g", "fat": "3.3 g"},
}


def fdc_get(endpoint, params=None):
    request_params = params.copy() if params else {}
    request_params["api_key"] = read_secret("FDC_API_KEY", "DEMO_KEY")

    response = requests.get(
        f"{FDC_BASE_URL}{endpoint}",
        params=request_params,
        timeout=5,
    )
    response.raise_for_status()
    return response.json()


def find_nutrient(food, nutrient_number):
    for nutrient in food.get("foodNutrients", []):
        if str(nutrient.get("nutrientId")) == nutrient_number:
            value = nutrient.get("value")
            unit = nutrient.get("unitName", "")
            if value is not None:
                return f"{round(value, 1)} {unit.lower()}"
    return "N/A"


def ingredient_search_terms(ingredient_name):
    cleaned_name = ingredient_name.lower()
    cleaned_name = re.sub(r"\([^)]*\)", " ", cleaned_name)
    cleaned_name = re.sub(r"[^a-zA-Z\s]", " ", cleaned_name)

    words_to_remove = {
        "fresh", "frozen", "dried", "large", "small", "medium", "chopped",
        "diced", "sliced", "minced", "grated", "ground", "boneless",
        "skinless", "cooked", "raw", "optional", "to", "taste",
    }
    words = [word for word in cleaned_name.split() if word and word not in words_to_remove]

    terms = []
    if words:
        terms.append(" ".join(words))
        terms.append(words[-1])
        if words[-1].endswith("s"):
            terms.append(words[-1][:-1])
    if ingredient_name.strip():
        terms.append(ingredient_name.strip())

    unique_terms = []
    for term in terms:
        if term and term not in unique_terms:
            unique_terms.append(term)
    return unique_terms


def has_macro_data(nutrition):
    return any(
        nutrition.get(key) != "N/A"
        for key in ("calories", "protein", "carbohydrates", "fat")
    )


def get_common_nutrition(ingredient_name):
    for term in ingredient_search_terms(ingredient_name):
        if term in COMMON_NUTRITION:
            nutrition = COMMON_NUTRITION[term].copy()
            nutrition["ingredient"] = ingredient_name
            nutrition["matched_food"] = f"{term.title()} (built-in estimate)"
            return nutrition
    return None


def get_usda_nutrition(ingredient_name):
    for search_term in ingredient_search_terms(ingredient_name):
        data = fdc_get("/foods/search", {"query": search_term, "pageSize": 5})
        foods = data.get("foods") or []

        for food in foods:
            nutrition = {
                "ingredient": ingredient_name,
                "matched_food": food.get("description", search_term).title(),
                "calories": find_nutrient(food, "1008"),
                "protein": find_nutrient(food, "1003"),
                "carbohydrates": find_nutrient(food, "1005"),
                "fat": find_nutrient(food, "1004"),
                "source": "USDA FoodData Central",
            }
            if has_macro_data(nutrition):
                return nutrition
    return None


def make_ai_nutrition_prompt(ingredient_name):
    return (
        "Estimate nutrition per 100 g for this ingredient: "
        f"{ingredient_name}. Return values as short strings such as '52 kcal' or '1.2 g'. "
        "Use 'Estimated by OpenAI' as the source."
    )


def get_openai_nutrition(ingredient_name):
    api_key = read_secret("OPENAI_API_KEY")
    if not api_key:
        return None

    model = read_secret("OPENAI_MODEL", "gpt-4.1-mini")
    response = requests.post(
        f"{OPENAI_BASE_URL}/responses",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "instructions": "You estimate basic nutrition for school recipe software.",
            "input": make_ai_nutrition_prompt(ingredient_name),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "nutrition_estimate",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "matched_food": {"type": "string"},
                            "calories": {"type": "string"},
                            "protein": {"type": "string"},
                            "carbohydrates": {"type": "string"},
                            "fat": {"type": "string"},
                            "source": {"type": "string"},
                        },
                        "required": [
                            "matched_food", "calories", "protein",
                            "carbohydrates", "fat", "source",
                        ],
                    },
                }
            },
        },
        timeout=12,
    )
    response.raise_for_status()
    data = response.json()
    text = data.get("output_text", "")

    if not text:
        for item in data.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    text = content.get("text", "")

    if not text:
        return None

    nutrition = json.loads(text)
    nutrition["ingredient"] = ingredient_name
    nutrition["matched_food"] = nutrition.get("matched_food", ingredient_name)
    nutrition["source"] = "Estimated by OpenAI"
    return nutrition


def get_ingredient_nutrition(ingredient_name):
    cache_key = ingredient_name.lower().strip()
    if cache_key in NUTRITION_CACHE:
        return NUTRITION_CACHE[cache_key]

    try:
        nutrition = get_usda_nutrition(ingredient_name)
    except requests.RequestException:
        nutrition = None

    if nutrition is None:
        try:
            nutrition = get_openai_nutrition(ingredient_name)
        except (requests.RequestException, json.JSONDecodeError, KeyError):
            nutrition = None

    if nutrition is None:
        nutrition = get_common_nutrition(ingredient_name)

    NUTRITION_CACHE[cache_key] = nutrition
    return nutrition


def get_recipe_ingredient_nutrition(recipe):
    nutrition_rows = []
    seen_ingredients = set()

    for ingredient in recipe.get("extendedIngredients", [])[:8]:
        name = ingredient.get("name", "").strip()
        if not name or name.lower() in seen_ingredients:
            continue

        seen_ingredients.add(name.lower())
        nutrition = get_ingredient_nutrition(name)
        if nutrition:
            nutrition_rows.append(nutrition)

    return nutrition_rows
