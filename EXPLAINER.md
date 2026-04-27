# EXPLAINER.md

## 1. The Ledger

**Balance calculation query:**

```python
credits = merchant.ledger_entries.filter(
    entry_type='credit'
).aggregate(total=Sum('amount_paise'))['total'] or 0

debits = merchant.ledger_entries.filter(
    entry_type='debit'
).aggregate(total=Sum('amount_paise'))['total'] or 0

available = credits - debits
```

We use a ledger model instead of a stored balance column because every credit and debit is recorded as an immutable entry, giving a full audit trail. You can prove the balance is correct at any point in time by replaying the entries.

Balance is calculated via PostgreSQL `SUM` aggregation, not Python arithmetic on fetched rows. Loading 50,000 ledger entries into Python to sum them would consume memory proportional to the number of entries and be orders of magnitude slower. PostgreSQL returns a single integer regardless of how many rows exist.

Credits are customer payments flowing in. Debits are confirmed payouts flowing out. A payout only creates a debit entry when it reaches `completed` state — not when it's created. This means a failed payout never touches the ledger and funds are never incorrectly debited.

---

## 2. The Lock

**Code that prevents concurrent overdraw:**

```python
with transaction.atomic():
    merchant_locked = Merchant.objects.select_for_update().get(id=merchant_id)

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
        return Response({'error': 'Insufficient balance'}, status=400)

    payout = Payout.objects.create(...)
```

This relies on PostgreSQL row-level locking via `SELECT FOR UPDATE`. When two simultaneous requests arrive for the same merchant, the first acquires a lock on the merchant row. The second request blocks at `select_for_update()` until the first transaction commits. By then, the balance has been updated and the second request correctly sees insufficient funds.

Python-level locking (threading locks, etc.) would not work here because Django runs multiple processes. A lock in one process is invisible to another. Only the database can coordinate across processes.

---

## 3. The Idempotency

The system uses a `unique_together` constraint on `(merchant, idempotency_key)` at the database level. Before creating a payout, we query for an existing payout with the same merchant and key:

```python
existing_payout = Payout.objects.filter(
    merchant=merchant,
    idempotency_key=idempotency_key
).first()

if existing_payout:
    return Response(PayoutSerializer(existing_payout).data, status=200)
```

If the first request is still in flight when the second arrives, the `unique_together` constraint at the database level prevents a duplicate insert — PostgreSQL will raise an integrity error. The second request will either find the existing record in the pre-check query or hit a DB constraint error, both resulting in no duplicate payout.

Keys are scoped per merchant — the same UUID used by two different merchants creates two separate valid payouts. Keys expire after 24 hours (can be enforced by filtering on `created_at` in the lookup query).

---

## 4. The State Machine

Legal transitions:
- `pending` → `processing` → `completed`
- `pending` → `processing` → `failed`

Illegal transitions are blocked by using filtered updates instead of direct saves:

```python
# This only updates if the payout is currently in PROCESSING state
# A completed payout will never match this filter
updated = Payout.objects.filter(
    id=payout_id,
    status=Payout.PROCESSING
).update(status=Payout.COMPLETED)
```

`failed` to `completed` is blocked because the filter requires `status=Payout.PROCESSING`. A failed payout will never match. The check is not in application logic with an if-statement — it is in the database query itself, making it impossible to bypass.

A failed payout returning funds is atomic with the state transition because the debit ledger entry is only created on `completed`. No debit was ever written for this payout, so the balance restores automatically when the payout leaves `pending` state.

---

## 5. The AI Audit

**What AI gave me:**

When generating the payout creation view, the AI initially wrote the balance check like this:

```python
merchant = Merchant.objects.get(id=merchant_id)
balance = merchant.calculate_balance()  # fetches all entries in Python
if amount > balance:
    return error
payout = Payout.objects.create(...)
```

**What was wrong:**

This is a classic check-then-act race condition. Between the balance check and the payout creation, another request could slip in, pass the same check, and both would succeed — overdrawing the balance. There is no lock held between the check and the write.

**What I replaced it with:**

Wrapped the entire check-and-create in `transaction.atomic()` with `select_for_update()` on the merchant row. The lock is held from the moment the balance is read until the payout is written, making it impossible for another request to read the same balance in between.

---

## AI Usage

Built with assistance from Claude. Every architectural decision — ledger model, row-level locking, idempotency via DB constraints, atomic state transitions — was understood, verified, and intentionally chosen. The AI audit section above is a real example of catching and correcting subtly wrong generated code.