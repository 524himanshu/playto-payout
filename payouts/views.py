from .tasks import process_payout
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Sum
from .models import Merchant, Payout, BankAccount, LedgerEntry
from .serializers import (
    MerchantSerializer, PayoutSerializer,
    CreatePayoutSerializer, LedgerEntrySerializer,
    BankAccountSerializer
)


class MerchantListView(APIView):
    def get(self, request):
        merchants = Merchant.objects.all()
        serializer = MerchantSerializer(merchants, many=True)
        return Response(serializer.data)


class MerchantDetailView(APIView):
    def get(self, request, merchant_id):
        try:
            merchant = Merchant.objects.get(id=merchant_id)
        except Merchant.DoesNotExist:
            return Response({'error': 'Merchant not found'}, status=404)

        serializer = MerchantSerializer(merchant)
        return Response(serializer.data)


class MerchantLedgerView(APIView):
    def get(self, request, merchant_id):
        try:
            merchant = Merchant.objects.get(id=merchant_id)
        except Merchant.DoesNotExist:
            return Response({'error': 'Merchant not found'}, status=404)

        entries = merchant.ledger_entries.order_by('-created_at')
        serializer = LedgerEntrySerializer(entries, many=True)
        return Response(serializer.data)


class MerchantBankAccountsView(APIView):
    def get(self, request, merchant_id):
        try:
            merchant = Merchant.objects.get(id=merchant_id)
        except Merchant.DoesNotExist:
            return Response({'error': 'Merchant not found'}, status=404)

        accounts = merchant.bank_accounts.filter(is_active=True)
        serializer = BankAccountSerializer(accounts, many=True)
        return Response(serializer.data)


class PayoutCreateView(APIView):
    def post(self, request, merchant_id):
        # Get idempotency key from header
        idempotency_key = request.headers.get('Idempotency-Key')
        if not idempotency_key:
            return Response(
                {'error': 'Idempotency-Key header is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            merchant = Merchant.objects.get(id=merchant_id)
        except Merchant.DoesNotExist:
            return Response({'error': 'Merchant not found'}, status=404)

        # Check if we've seen this idempotency key before
        existing_payout = Payout.objects.filter(
            merchant=merchant,
            idempotency_key=idempotency_key
        ).first()

        if existing_payout:
            # Return exact same response as the first call
            return Response(
                PayoutSerializer(existing_payout).data,
                status=status.HTTP_200_OK
            )

        # Validate request body
        serializer = CreatePayoutSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        amount_paise = serializer.validated_data['amount_paise']
        bank_account_id = serializer.validated_data['bank_account_id']

        try:
            bank_account = BankAccount.objects.get(
                id=bank_account_id,
                merchant=merchant,
                is_active=True
            )
        except BankAccount.DoesNotExist:
            return Response({'error': 'Bank account not found'}, status=404)

        # THIS IS THE CRITICAL PART - database level locking
        with transaction.atomic():
            # Lock the merchant row so no other request can touch it
            # until this transaction is done
            merchant_locked = Merchant.objects.select_for_update().get(id=merchant_id)

            # Calculate available balance inside the lock
            credits = merchant_locked.ledger_entries.filter(
                entry_type='credit'
            ).aggregate(total=Sum('amount_paise'))['total'] or 0

            debits = merchant_locked.ledger_entries.filter(
                entry_type='debit'
            ).aggregate(total=Sum('amount_paise'))['total'] or 0

            held = merchant_locked.payouts.filter(
                status='pending'
            ).aggregate(total=Sum('amount_paise'))['total'] or 0

            available = credits - debits - held

            if amount_paise > available:
                return Response(
                    {'error': f'Insufficient balance. Available: {available} paise'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create payout - funds are now held
            payout = Payout.objects.create(
                merchant=merchant_locked,
                bank_account=bank_account,
                amount_paise=amount_paise,
                status=Payout.PENDING,
                idempotency_key=idempotency_key
            )
            
        process_payout.delay(payout.id)    

        return Response(PayoutSerializer(payout).data, status=status.HTTP_201_CREATED)


class PayoutListView(APIView):
    def get(self, request, merchant_id):
        try:
            merchant = Merchant.objects.get(id=merchant_id)
        except Merchant.DoesNotExist:
            return Response({'error': 'Merchant not found'}, status=404)

        payouts = merchant.payouts.order_by('-created_at')
        serializer = PayoutSerializer(payouts, many=True)
        return Response(serializer.data)


class PayoutDetailView(APIView):
    def get(self, request, merchant_id, payout_id):
        try:
            payout = Payout.objects.get(id=payout_id, merchant_id=merchant_id)
        except Payout.DoesNotExist:
            return Response({'error': 'Payout not found'}, status=404)

        serializer = PayoutSerializer(payout)
        return Response(serializer.data)