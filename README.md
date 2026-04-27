# Playto Payout Engine

A minimal payout engine built for the Playto Founding Engineer Challenge. Handles merchant balances, payout requests, background processing, and simulated bank settlement.

## Stack

- **Backend:** Django + Django REST Framework
- **Database:** PostgreSQL
- **Background Jobs:** Celery + Redis
- **Frontend:** React + Tailwind CSS

## How it works

Money flows one way: international customer pays in USD, Playto collects, merchant withdraws to Indian bank account in INR.

Each merchant has a ledger — every credit (incoming payment) and debit (confirmed payout) is recorded as an immutable entry. Balance is always derived from the ledger, never stored directly.

When a merchant requests a payout:
1. API acquires a row-level lock on the merchant via `SELECT FOR UPDATE`
2. Balance is calculated inside the lock
3. If sufficient, a payout is created in `pending` state
4. Celery picks it up and simulates bank settlement (70% success, 20% fail, 10% hang)
5. On success, a debit ledger entry is created atomically with the state transition
6. On failure, no debit is written — funds return automatically

## Local Setup

### Prerequisites
- Python 3.12+
- PostgreSQL
- Redis

### Backend

```bash
python -m venv venv
venv\Scripts\activate
pip install django djangorestframework psycopg2-binary celery redis
```

Create a PostgreSQL database called `playto_payout`. Update `config/settings.py` with your credentials.

```bash
python manage.py migrate
python manage.py shell -c "from payouts.seed import run; run()"
python manage.py runserver
```

### Celery Worker

Open a second terminal:

```bash
celery -A config worker --loglevel=info -P solo
```

### Frontend

```bash
cd frontend
npm install
npm start
```

Visit `http://localhost:3000`

## Running Tests

```bash
python manage.py test payouts
```

Two tests included:
- **Idempotency test** — same key returns same payout, no duplicate created
- **Concurrency test** — two simultaneous overdraw attempts, exactly one succeeds

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/merchants/` | List all merchants with balances |
| GET | `/api/v1/merchants/:id/` | Merchant detail |
| GET | `/api/v1/merchants/:id/ledger/` | Ledger entries |
| GET | `/api/v1/merchants/:id/bank-accounts/` | Bank accounts |
| POST | `/api/v1/merchants/:id/payouts/create/` | Request payout |
| GET | `/api/v1/merchants/:id/payouts/` | Payout history |

POST `/api/v1/merchants/:id/payouts/create/` requires:
- Header: `Idempotency-Key: <uuid>`
- Body: `{ "amount_paise": 100000, "bank_account_id": 1 }`

## Architecture Decisions

See [EXPLAINER.md](./EXPLAINER.md)