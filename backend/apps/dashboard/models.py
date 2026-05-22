from django.db import models
from django.conf import settings


class DashboardWidget(models.Model):
    WIDTH_CHOICES = [("half", "Half"), ("full", "Full")]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dashboard_widgets",
    )
    widget_key = models.CharField(max_length=100)
    position = models.PositiveIntegerField()
    is_visible = models.BooleanField(default=True)
    width = models.CharField(max_length=10, choices=WIDTH_CHOICES, default="half")

    class Meta:
        unique_together = ("user", "widget_key")
        ordering = ["position"]

    def __str__(self):
        return f"{self.user} — {self.widget_key} (pos {self.position})"
