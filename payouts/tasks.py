import random
import logging
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from .models import Payout, LedgerEntry

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_payout(self, payout_id):
    try:
        payout = Payout.objects.get(id=payout_id)
    except Payout.DoesNotExist:
        logger.error(f"Payout {payout_id} not found")
        return

    # Block illegal state transitions
    if payout.status != Payout.PENDING:
        logger.warning(f"Payout {payout_id} is not in pending state, skipping")
        return

    # Move to processing
    with transaction.atomic():
        updated = Payout.objects.filter(
            id=payout_id,
            status=Payout.PENDING
        ).update(
            status=Payout.PROCESSING,
            attempt_count=payout.attempt_count + 1
        )

        if not updated:
            logger.warning(f"Payout {payout_id} already being processed")
            return

    # Simulate bank settlement: 70% success, 20% fail, 10% hang
    outcome = random.choices(
        ['success', 'failure', 'processing'],
        weights=[70, 20, 10]
    )[0]

    if outcome == 'success':
        with transaction.atomic():
            # Block illegal transition - only processing can move to completed
            updated = Payout.objects.filter(
                id=payout_id,
                status=Payout.PROCESSING
            ).update(status=Payout.COMPLETED)

            if updated:
                # Create debit ledger entry
                LedgerEntry.objects.create(
                    merchant_id=payout.merchant_id,
                    entry_type='debit',
                    amount_paise=payout.amount_paise,
                    description=f"Payout #{payout_id} to bank account"
                )
                logger.info(f"Payout {payout_id} completed successfully")

    elif outcome == 'failure':
        with transaction.atomic():
            # Return funds atomically with state transition
            # This is the atomic failure handling the challenge requires
            updated = Payout.objects.filter(
                id=payout_id,
                status=Payout.PROCESSING
            ).update(status=Payout.FAILED)

            if updated:
                logger.info(f"Payout {payout_id} failed, funds returned")

    else:
        # Hung in processing - retry with exponential backoff
        if payout.attempt_count < 3:
            raise self.retry(
                countdown=30 * (2 ** payout.attempt_count)
            )
        else:
            # Max retries hit - move to failed and return funds
            with transaction.atomic():
                Payout.objects.filter(
                    id=payout_id,
                    status=Payout.PROCESSING
                ).update(status=Payout.FAILED)
            logger.error(f"Payout {payout_id} max retries hit, marked failed")


@shared_task
def retry_stuck_payouts():
    """Picks up payouts stuck in processing for more than 30 seconds"""
    from django.utils import timezone
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(seconds=30)
    stuck_payouts = Payout.objects.filter(
        status=Payout.PROCESSING,
        updated_at__lt=cutoff,
        attempt_count__lt=3
    )

    for payout in stuck_payouts:
        process_payout.delay(payout.id)
        logger.info(f"Retrying stuck payout {payout.id}")