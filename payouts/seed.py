from django.db import transaction
from payouts.models import Merchant, BankAccount, LedgerEntry


def run():
    with transaction.atomic():
        # Clear existing data
        LedgerEntry.objects.all().delete()
        BankAccount.objects.all().delete()
        Merchant.objects.all().delete()

        # Create merchants
        m1 = Merchant.objects.create(name="Ravi Freelancer", email="ravi@example.com")
        m2 = Merchant.objects.create(name="Priya Agency", email="priya@example.com")
        m3 = Merchant.objects.create(name="Arjun Designs", email="arjun@example.com")

        # Create bank accounts
        BankAccount.objects.create(
            merchant=m1, account_number="1234567890",
            ifsc_code="HDFC0001234", account_holder_name="Ravi Kumar"
        )
        BankAccount.objects.create(
            merchant=m2, account_number="9876543210",
            ifsc_code="ICIC0005678", account_holder_name="Priya Sharma"
        )
        BankAccount.objects.create(
            merchant=m3, account_number="1122334455",
            ifsc_code="SBIN0009012", account_holder_name="Arjun Mehta"
        )

        # Seed credits (simulated customer payments)
        LedgerEntry.objects.create(merchant=m1, entry_type='credit', amount_paise=500000, description="Payment from client US")
        LedgerEntry.objects.create(merchant=m1, entry_type='credit', amount_paise=300000, description="Payment from client UK")
        LedgerEntry.objects.create(merchant=m2, entry_type='credit', amount_paise=1000000, description="Agency retainer - April")
        LedgerEntry.objects.create(merchant=m2, entry_type='credit', amount_paise=750000, description="Project milestone payment")
        LedgerEntry.objects.create(merchant=m3, entry_type='credit', amount_paise=250000, description="Logo design payment")
        LedgerEntry.objects.create(merchant=m3, entry_type='credit', amount_paise=450000, description="Brand kit delivery")

        print("Seeded 3 merchants with bank accounts and credit history.")