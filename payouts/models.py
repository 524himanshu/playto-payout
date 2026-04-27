from django.db import models


class Merchant(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class LedgerEntry(models.Model):
    CREDIT = 'credit'
    DEBIT = 'debit'
    ENTRY_TYPES = [(CREDIT, 'Credit'), (DEBIT, 'Debit')]

    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name='ledger_entries')
    entry_type = models.CharField(max_length=10, choices=ENTRY_TYPES)
    amount_paise = models.BigIntegerField()
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.entry_type} {self.amount_paise} for {self.merchant.name}"


class BankAccount(models.Model):
    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name='bank_accounts')
    account_number = models.CharField(max_length=50)
    ifsc_code = models.CharField(max_length=20)
    account_holder_name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.account_holder_name} - {self.account_number}"


class Payout(models.Model):
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'

    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (PROCESSING, 'Processing'),
        (COMPLETED, 'Completed'),
        (FAILED, 'Failed'),
    ]

    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name='payouts')
    bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT)
    amount_paise = models.BigIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    idempotency_key = models.CharField(max_length=255)
    attempt_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('merchant', 'idempotency_key')]

    def __str__(self):
        return f"Payout {self.id} - {self.status}"