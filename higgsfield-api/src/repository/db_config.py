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


TORTOISE_ORM = {
    "connections": {"default": "sqlite://src/repository/db/higgsfield.db"},
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
