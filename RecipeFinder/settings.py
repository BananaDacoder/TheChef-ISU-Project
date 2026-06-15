import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "recipes.db")
SECRETS_PATH = os.path.join(BASE_DIR, "secrets.txt")

MEALDB_BASE_URL = "https://www.themealdb.com/api/json/v1/1"
FDC_BASE_URL = "https://api.nal.usda.gov/fdc/v1"
OPENAI_BASE_URL = "https://api.openai.com/v1"


def read_secret(secret_name, default_value=""):
    """Read one setting from the environment or secrets.txt."""
    environment_value = os.environ.get(secret_name)
    if environment_value:
        return environment_value

    if not os.path.exists(SECRETS_PATH):
        return default_value

    with open(SECRETS_PATH, "r", encoding="utf-8") as secrets_file:
        for line in secrets_file:
            clean_line = line.strip()
            if clean_line.startswith(f"{secret_name}="):
                return clean_line.split("=", 1)[1].strip()

    return default_value
