import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DB_PATH = os.getenv("DB_PATH", "data/marketplace.db")

try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
except ValueError:
    ADMIN_ID = 0

ADMIN_LOGIN = os.getenv("ADMIN_LOGIN", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change_me")

try:
    FREE_CATEGORY_LIMIT = int(os.getenv("FREE_CATEGORY_LIMIT", "3"))
except ValueError:
    FREE_CATEGORY_LIMIT = 3

try:
    EXTRA_CATEGORY_PRICE = int(os.getenv("EXTRA_CATEGORY_PRICE", "300"))
except ValueError:
    EXTRA_CATEGORY_PRICE = 300
