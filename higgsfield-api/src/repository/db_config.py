from pathlib import Path

# from config import DB_USER, DB_PASSWORD, DB_HOST, DB_NAME, DB_SOCKET

# TORTOISE_ORM = {
#     "connections": {
#         'default': f"mysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}?unix_socket={DB_SOCKET}"
#     },
#     "apps": {
#         "models": {
#             "models": ["src.repository.models.task", "src.repository.models.client"],
#             "default_connection": "default",
#          }
#     },
#     "use_tz": False,
#     "timezone": "Europe/Moscow"
# }


_REPO_DIR = Path(__file__).resolve().parent
_DB_DIR = _REPO_DIR / "db"
_DB_DIR.mkdir(parents=True, exist_ok=True)
_DB_PATH = _DB_DIR / "higgsfield.db"


TORTOISE_ORM = {
    "connections": {"default": f"sqlite://{_DB_PATH}"},
    "apps": {
        "models": {
            "models": [
                "src.repository.models.task",
                "src.repository.models.client",
                "src.repository.models.account",
            ],
            "default_connection": "default",
        }
    },
    "use_tz": False,
    "timezone": "UTC",
}
