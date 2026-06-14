from rest_framework import serializers
from balance_engine.models import BalanceSnapshot

class BalanceSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = BalanceSnapshot
        fields = ["id", "group", "snapshot_date", "payload_json", "created_at"]
