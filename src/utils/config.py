
import os
from dotenv import load_dotenv
load_dotenv()
DB_PATH = os.getenv("UBI_DB_PATH", "data/ubi.db")
SECRET_KEY = os.getenv("UBI_SECRET_KEY", "dev_secret")
API_KEY = os.getenv("UBI_API_KEY", "dev_api_key_change_me")
JWT_EXPIRES_MIN = int(os.getenv("UBI_JWT_EXPIRES_MIN", "60"))
