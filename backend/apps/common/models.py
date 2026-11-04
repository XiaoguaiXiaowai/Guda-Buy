"""所有业务模型的基类：对外 public_id、审计时间与软删除。"""

import uuid

from django.db import models
from django.utils import timezone


class BaseModel(models.Model):
    public_id = models.CharField("对外标识", max_length=32, unique=True, editable=False)
    created_at = models.DateTimeField("创建时间", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)
    is_deleted = models.BooleanField("是否删除", default=False)
    deleted_at = models.DateTimeField("删除时间", null=True, blank=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = uuid.uuid4().hex
        return super().save(*args, **kwargs)

    def soft_delete(self, using: str | None = None) -> None:
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(using=using, update_fields=["is_deleted", "deleted_at", "updated_at"])
