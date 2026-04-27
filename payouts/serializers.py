from rest_framework import serializers
from .models import Merchant, LedgerEntry, BankAccount, Payout
from django.db.models import Sum


class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = ['id', 'entry_type', 'amount_paise', 'description', 'created_at']


class BankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = ['id', 'account_number', 'ifsc_code', 'account_holder_name', 'is_active']


class MerchantSerializer(serializers.ModelSerializer):
    available_balance_paise = serializers.SerializerMethodField()
    held_balance_paise = serializers.SerializerMethodField()

    class Meta:
        model = Merchant
        fields = ['id', 'name', 'email', 'available_balance_paise', 'held_balance_paise', 'created_at']

    def get_available_balance_paise(self, obj):
        from django.db.models import Sum
        credits = obj.ledger_entries.filter(
            entry_type='credit'
        ).aggregate(total=Sum('amount_paise'))['total'] or 0

        debits = obj.ledger_entries.filter(
            entry_type='debit'
        ).aggregate(total=Sum('amount_paise'))['total'] or 0

        return credits - debits

    def get_held_balance_paise(self, obj):
        held = obj.payouts.filter(
            status='pending'
        ).aggregate(total=Sum('amount_paise'))['total'] or 0
        return held


class PayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payout
        fields = ['id', 'amount_paise', 'status', 'bank_account', 'created_at', 'updated_at']


class CreatePayoutSerializer(serializers.Serializer):
    amount_paise = serializers.IntegerField(min_value=1)
    bank_account_id = serializers.IntegerField()

    def validate_amount_paise(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive.")
        return value    