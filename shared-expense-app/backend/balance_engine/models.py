from django.db import models

class BalanceSnapshot(models.Model):
    group = models.ForeignKey("groups.Group", on_delete=models.CASCADE, related_name="balance_snapshots")
    snapshot_date = models.DateTimeField(auto_now_add=True)
    payload_json = models.JSONField(help_text="Full group balances JSON snapshot")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-snapshot_date"]

    def __str__(self):
        return f"Balance Snapshot for {self.group.name} at {self.snapshot_date}"
