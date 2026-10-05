import uuid
from django.db import models
from django.utils import timezone


class BaseUUIDModel(models.Model):
    """
    Abstract base model using UUIDs and timestamp.

    Provides consistent IDs and ordering across the Missal domain.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True