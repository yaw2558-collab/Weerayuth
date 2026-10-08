# Firestore schema (thai-customs product)

Database: `(default)` in `asia-southeast1`.

## users/{uid}

| field    | type      | notes                          |
|----------|-----------|--------------------------------|
| email    | string    | from Firebase Auth (optional)  |
| credits  | number    | current balance (THB credits)  |
| created  | timestamp | first seen                     |
| consent  | timestamp | PDPA consent time (Phase 1+)   |

## credits_ledger/{auto-id}

| field   | type      | notes                              |
|---------|-----------|------------------------------------|
| user_id | string    |                                    |
| ts      | timestamp | server time                        |
| delta   | number    | +topup / -usage (THB credits)      |
| reason  | string    | `topup:stripe:<id>` / `chat:<log>` |

## usage_logs/{auto-id}

Written by `POST /chat` (Phase 0+).

| field             | type      | notes                        |
|-------------------|-----------|------------------------------|
| user_id           | string    |                              |
| ts                | timestamp | server time                  |
| session_id        | string    |                              |
| question          | string    | full user message            |
| answer_chars      | number    | length of answer             |
| prompt_tokens     | number    | summed usage_metadata        |
| candidates_tokens | number    | summed usage_metadata        |
| thoughts_tokens   | number    | summed usage_metadata        |
| grounding_calls   | number    | events with grounding data   |
| latency_s         | number    | end-to-end seconds           |
| est_cost_usd      | number    | priced estimate (calibrated) |

## payments/{stripe_session_id} (Phase 2+)

Doc id = Stripe Checkout Session id (webhook idempotency key).

| field      | type      | notes                          |
|------------|-----------|--------------------------------|
| user_id    | string    |                                |
| ts         | timestamp | webhook time                   |
| provider   | string    | `stripe`                       |
| livemode   | boolean   | true = real money              |
| amount_thb | number    | charged amount                 |
| credits    | number    | granted credits                |
| status     | string    | `succeeded` / `failed`         |
| reason     | string    | set when `failed`              |
