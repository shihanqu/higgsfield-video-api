import secrets
from typing import TYPE_CHECKING

from tortoise import Model, fields

if TYPE_CHECKING:
    from .task import Task


class Client(Model):
    id = fields.IntField(pk=True)
    username = fields.TextField(null=False)
    password = fields.TextField(null=False)
    url = fields.TextField(null=True)
    token = fields.CharField(
        default=lambda: secrets.token_hex(16), unique=True, db_index=True, max_length=32
    )
    is_admin = fields.BooleanField(default=False)
    is_active = fields.BooleanField(default=True)
    tasks: fields.ReverseRelation["Task"]

    class Meta:
        table = "client"
