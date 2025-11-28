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

# ─────────────────────────────────────────────────────────────────────────────
# Scheduler Settings
# ─────────────────────────────────────────────────────────────────────────────

# How often to poll for task status updates (seconds)
TASK_STATUS_POLL_INTERVAL = 5

# Max parallel task status check jobs (increase for high concurrency)
TASK_STATUS_MAX_INSTANCES = 5

# Minimum delay between individual status check API calls (seconds)
# Prevents hammering the Higgsfield API when checking multiple tasks
TASK_STATUS_REQUEST_DELAY = 0.25

# How often to check for new pending tasks (seconds)
TASK_QUEUE_POLL_INTERVAL = 3

# How often to attempt result delivery to webhooks (seconds)
RESULT_DELIVERY_INTERVAL = 2

# ─────────────────────────────────────────────────────────────────────────────
# Server Settings (used by run_server.py)
# ─────────────────────────────────────────────────────────────────────────────

# Can also be set via environment variables: SERVER_HOST, SERVER_PORT, SERVER_RELOAD
SERVER_HOST = env.str("SERVER_HOST", default="0.0.0.0")
SERVER_PORT = env.int("SERVER_PORT", default=8018)
SERVER_RELOAD = env.bool("SERVER_RELOAD", default=True)