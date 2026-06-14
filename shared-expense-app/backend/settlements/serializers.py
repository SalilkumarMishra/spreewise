from rest_framework import serializers
from django.contrib.auth import get_user_model
from settlements.models import Settlement, SettlementSnapshot

User = get_user_model()

class SettlementSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = SettlementSnapshot
        fields = ["id", "version", "payload_json", "created_at"]


class SettlementSerializer(serializers.ModelSerializer):
    payer_username = serializers.CharField(source="payer.username", read_only=True)
    receiver_username = serializers.CharField(source="receiver.username", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)

    class Meta:
        model = Settlement
        fields = [
            "id", "reference_id", "group", "group_name", 
            "payer", "payer_username", "receiver", "receiver_username",
            "amount", "currency", "original_amount", "original_currency",
            "payment_date", "settlement_category", "source", "status",
            "is_archived", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "reference_id", "is_archived", "created_at", "updated_at"]


class SettlementDetailSerializer(serializers.ModelSerializer):
    payer_username = serializers.CharField(source="payer.username", read_only=True)
    receiver_username = serializers.CharField(source="receiver.username", read_only=True)
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)
    snapshots = SettlementSnapshotSerializer(many=True, read_only=True)

    class Meta:
        model = Settlement
        fields = [
            "id", "reference_id", "group", "group_name",
            "payer", "payer_username", "receiver", "receiver_username",
            "amount", "currency", "original_amount", "original_currency",
            "payment_date", "notes", "settlement_category", "source", "status",
            "is_archived", "created_by", "created_by_username",
            "created_at", "updated_at", "snapshots"
        ]
        read_only_fields = ["id", "reference_id", "is_archived", "created_by", "created_at", "updated_at"]


class SettlementCreateSerializer(serializers.Serializer):
    group_id = serializers.IntegerField()
    payer_id = serializers.IntegerField()
    receiver_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    currency = serializers.CharField(max_length=10, default="INR")
    original_amount = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, allow_null=True)
    original_currency = serializers.CharField(max_length=10, required=False, allow_blank=True, default="INR")
    payment_date = serializers.DateField()
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    settlement_category = serializers.ChoiceField(
        choices=["direct_payment", "bank_transfer", "cash", "upi", "imported"],
        default="direct_payment"
    )
    source = serializers.ChoiceField(
        choices=["manual", "csv_import", "system"],
        default="manual"
    )
    status = serializers.ChoiceField(
        choices=["active", "disputed", "import_review"],
        default="active"
    )

    def validate_payer_id(self, value):
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError(f"User with id={value} does not exist.")
        return value

    def validate_receiver_id(self, value):
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError(f"User with id={value} does not exist.")
        return value
