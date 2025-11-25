from typing import TYPE_CHECKING

from tortoise import Model, fields

if TYPE_CHECKING:
    from .task import Task


class HiggsfieldAccount(Model):
    id = fields.IntField(pk=True)

    username = fields.CharField(max_length=100, unique=True, null=True)
    is_active = fields.BooleanField(default=True)

    balance = fields.BigIntField(default=0)
    subscription = fields.CharField(max_length=100, default="free")
    subscription_end_at = fields.DatetimeField(null=True)

    cookies_json = fields.JSONField()

    low_balance_alert = fields.BooleanField(default=False)

    payment_retry = fields.IntField(default=10)
    next_payment_check = fields.DatetimeField(null=True)

    suspended_until = fields.DatetimeField(null=True)

    last_updated_at = fields.DatetimeField(auto_now_add=True, null=True)
    last_used_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    tasks: fields.ReverseRelation["Task"]
