from tortoise import Tortoise

from .db_config import TORTOISE_ORM
from .models.task import Task


async def init_db():
    await Tortoise.init(config=TORTOISE_ORM)
    await Tortoise.generate_schemas()


async def update_statusses():
    await Task.filter(status="starting").update(status="pending")

    await Task.filter(status="success_retry").update(status="success")
    await Task.filter(status="failed_retry").update(status="failed")
