from django.test import TestCase
from django.db import transaction
from rest_framework.test import APIClient
from concurrent.futures import ThreadPoolExecutor, as_completed
from .models import Merchant, BankAccount, LedgerEntry, Payout
from django.test import TestCase, TransactionTestCase



def setup_merchant(balance_paise=1000000):
    merchant = Merchant.objects.create(
        name="Test Merchant",
        email=f"test_{Merchant.objects.count()}@example.com"
    )
    BankAccount.objects.create(
        merchant=merchant,
        account_number="1234567890",
        ifsc_code="HDFC0001234",
        account_holder_name="Test User"
    )
    LedgerEntry.objects.create(
        merchant=merchant,
        entry_type='credit',
        amount_paise=balance_paise,
        description="Initial credit"
    )
    return merchant


class IdempotencyTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.merchant = setup_merchant()
        self.bank_account = self.merchant.bank_accounts.first()

    def test_same_idempotency_key_returns_same_payout(self):
        """Two requests with same key should return same payout, not create two"""
        payload = {
            "amount_paise": 100000,
            "bank_account_id": self.bank_account.id
        }
        headers = {"HTTP_IDEMPOTENCY_KEY": "unique-key-abc"}

        response1 = self.client.post(
            f"/api/v1/merchants/{self.merchant.id}/payouts/create/",
            payload, format='json', **headers
        )
        response2 = self.client.post(
            f"/api/v1/merchants/{self.merchant.id}/payouts/create/",
            payload, format='json', **headers
        )

        # Both should succeed
        self.assertIn(response1.status_code, [200, 201])
        self.assertIn(response2.status_code, [200, 201])

        # Should be the same payout ID
        self.assertEqual(response1.data['id'], response2.data['id'])

        # Only one payout should exist in DB
        self.assertEqual(
            Payout.objects.filter(merchant=self.merchant).count(), 1
        )


class ConcurrencyTest(TransactionTestCase):
    def setUp(self):
        self.merchant = setup_merchant(balance_paise=1000000)
        self.bank_account = self.merchant.bank_accounts.first()

    def test_concurrent_payouts_cannot_overdraw(self):
        """Two simultaneous 600000 paise requests against 1000000 balance.
        Exactly one should succeed, one should fail."""

        results = []

        def make_payout_request(key):
            client = APIClient()
            payload = {
                "amount_paise": 600000,
                "bank_account_id": self.bank_account.id
            }
            response = client.post(
                f"/api/v1/merchants/{self.merchant.id}/payouts/create/",
                payload, format='json',
                **{"HTTP_IDEMPOTENCY_KEY": key}
            )
            return response.status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(make_payout_request, "concurrent-key-1"),
                executor.submit(make_payout_request, "concurrent-key-2"),
            ]
            for future in as_completed(futures):
                results.append(future.result())

        success_count = results.count(201)
        failure_count = results.count(400)

        self.assertEqual(success_count, 1, f"Expected 1 success, got {results}")
        self.assertEqual(failure_count, 1, f"Expected 1 failure, got {results}")

        self.assertEqual(
            Payout.objects.filter(merchant=self.merchant).count(), 1
        )