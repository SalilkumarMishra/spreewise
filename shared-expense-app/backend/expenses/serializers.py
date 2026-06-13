from rest_framework import serializers
from django.contrib.auth import get_user_model
from expenses.models import Expense, ExpenseParticipant, ExpenseSplit, ExpenseSnapshot

User = get_user_model()


class ExpenseParticipantSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    user_id = serializers.IntegerField(source="user.id", read_only=True)

    class Meta:
        model = ExpenseParticipant
        fields = ["id", "user_id", "username"]


class ExpenseSplitSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    user_id = serializers.IntegerField(source="user.id", read_only=True)

    class Meta:
        model = ExpenseSplit
        fields = [
            "id", "user_id", "username",
            "percentage_value", "shares_value", "exact_amount",
            "calculated_amount",
        ]


class ExpenseSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseSnapshot
        fields = ["id", "version", "payload_json", "created_at"]


class ExpenseSerializer(serializers.ModelSerializer):
    """Summary serializer for list views."""
    paid_by_username = serializers.CharField(source="paid_by.username", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)

    class Meta:
        model = Expense
        fields = [
            "id", "group", "group_name", "title", "amount", "currency",
            "original_amount", "original_currency",
            "expense_date", "paid_by", "paid_by_username",
            "split_type", "status", "expense_category", "source",
            "is_archived", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "is_archived", "created_at", "updated_at"]


class ExpenseDetailSerializer(serializers.ModelSerializer):
    """Full detail serializer including nested participants, splits, and snapshots."""
    paid_by_username = serializers.CharField(source="paid_by.username", read_only=True)
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)
    participants = ExpenseParticipantSerializer(many=True, read_only=True)
    splits = ExpenseSplitSerializer(many=True, read_only=True)
    snapshots = ExpenseSnapshotSerializer(many=True, read_only=True)
    participant_count = serializers.SerializerMethodField()

    class Meta:
        model = Expense
        fields = [
            "id", "group", "group_name", "title", "description",
            "amount", "currency", "original_amount", "original_currency",
            "expense_date", "paid_by", "paid_by_username",
            "split_type", "status", "expense_category", "source",
            "notes", "is_archived",
            "created_by", "created_by_username",
            "created_at", "updated_at",
            "participant_count",
            "participants", "splits", "snapshots",
        ]
        read_only_fields = ["id", "is_archived", "created_by", "created_at", "updated_at"]

    def get_participant_count(self, obj):
        return obj.participants.count()


# ------------------------------------------------------------------
# Write serializer – used for POST (create) and PUT (update)
# ------------------------------------------------------------------

class SplitInputSerializer(serializers.Serializer):
    """Nested input for a single user's split data."""
    user_id = serializers.IntegerField()
    percentage_value = serializers.DecimalField(
        max_digits=7, decimal_places=4, required=False, allow_null=True
    )
    shares_value = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )
    exact_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True
    )


class ExpenseCreateSerializer(serializers.Serializer):
    """
    Write serializer for creating/updating expenses.
    Delegates business logic to expense_service.
    """
    group_id = serializers.IntegerField()
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    currency = serializers.CharField(max_length=10, default="INR")
    original_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True
    )
    original_currency = serializers.CharField(
        max_length=10, required=False, allow_blank=True, default="INR"
    )
    expense_date = serializers.DateField()
    paid_by_id = serializers.IntegerField()
    split_type = serializers.ChoiceField(
        choices=["equal", "percentage", "shares", "exact"]
    )
    status = serializers.ChoiceField(
        choices=["active", "disputed", "import_review"],
        default="active"
    )
    expense_category = serializers.CharField(max_length=50, default="general")
    source = serializers.ChoiceField(
        choices=["manual", "csv_import", "system"],
        default="manual"
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    participant_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    splits = SplitInputSerializer(many=True, required=False, default=list)

    def validate_paid_by_id(self, value):
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError(f"User with id={value} does not exist.")
        return value

    def validate_participant_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Duplicate participant IDs are not allowed.")
        missing = [uid for uid in value if not User.objects.filter(id=uid).exists()]
        if missing:
            raise serializers.ValidationError(f"Users not found: {missing}")
        return value
