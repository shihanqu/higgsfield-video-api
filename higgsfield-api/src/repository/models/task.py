import uuid
from datetime import datetime, timezone

from tortoise import Model, fields


class Task(Model):
    id = fields.IntField(pk=True)
    task_id = fields.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    api_task_id = fields.CharField(null=True, max_length=50)
    api_status = fields.CharField(max_length=20, null=True)
    type = fields.CharField(max_length=20)
    status = fields.CharField(
        max_length=20,
        choices=[
            ("pending", "pending"),
            ("starting", "starting"),
            ("processing", "processing"),
            ("success", "success"),
            ("failed", "failed"),
            ("retry", "retry"),
        ],
        default="pending",
    )
    parameters_json = fields.JSONField()
    metadata = fields.JSONField(default=dict)
    result = fields.JSONField(default=list)
    message = fields.TextField(null=True)  # Error message or status details
    is_delivered = fields.BooleanField(default=False)

    created_at = fields.DatetimeField(auto_now_add=True)
    started_at = fields.DatetimeField(null=True)
    finished_at = fields.DatetimeField(null=True)
    delivered_at = fields.DatetimeField(null=True)
    retries = fields.IntField(default=0)

    account = fields.ForeignKeyField(
        "models.HiggsfieldAccount", related_name="tasks", null=True
    )
    client = fields.ForeignKeyField("models.Client", related_name="tasks")

    class Meta:
        table = "task"

    def update_datetime(self):
        current_time = datetime.now(timezone.utc)
        if self.status == "processing" and self.started_at is None:
            self.started_at = current_time
        elif self.status in ["success", "failed"] and self.finished_at is None:
            self.finished_at = current_time
        elif self.is_delivered and self.delivered_at is None:
            self.delivered_at = current_time
