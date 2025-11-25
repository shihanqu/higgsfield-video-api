from environs import Env

env = Env()
env.read_env()

APP_ORIGIN = "https://higgsfield.ai"
CLERK_BASE = "https://clerk.higgsfield.ai"
CLERK_APIVER = "2025-04-10"
CLERK_JSVER = "5.86.0"
STORAGE = "secret_keys/auth.json"

BASE_STORAGE_PATH = "/mnt/newdisk/higgsfield"
IMAGE_STORAGE_PATH = f"{BASE_STORAGE_PATH}/images"

DB_HOST = env("DB_HOST", default="localhost")
DB_SOCKET = env("DB_SOCKET", default="")
DB_USER = env("DB_USER", default="")
DB_PASSWORD = env("DB_PASSWORD", default="")
DB_NAME = env("DB_NAME", default="")
UUID_TEST_CHECK = env("UUID_TEST_CHECK", default="test-uuid")
