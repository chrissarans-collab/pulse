# Spend Coach: a nudge after each payment (full-stack)

**Who it's for:** anyone who pays by UPI or card and will accept one nudge after the payment.

## What is in this zip
- `app.py` + `static/index.html`: full-stack version (Python API + SQLite + UPI-style frontend)
- `standalone/spend-coach-single-file.html`: same app in ONE file, just double-click (no Python, saves in the browser)
- `run-windows.bat` / `run-mac-linux.sh`: one-click start for the full-stack version
- `DEPLOY.md`, `render.yaml`, `Procfile`, `requirements.txt`: put it online for free on Render

## Run it (no pip install needed, Python 3 only)
1. Keep this structure:
   ```
   spend-coach-app/
   ├── app.py            backend: REST API + agent + SQLite
   ├── static/index.html frontend: UPI-style phone + dashboard
   └── spend_coach.db    database (created automatically on first run)
   ```
2. In a terminal inside `spend-coach-app`: `python app.py` (Windows: `py app.py`, Mac/Linux: `python3 app.py`)
3. Open http://localhost:8000 and keep the terminal open. If port 8000 is busy: `PORT=8080 python app.py`.

## Architecture
Browser (HTML/CSS/JS) -> REST API (Python) -> SQLite

| Endpoint | Purpose |
|---|---|
| GET /api/state | caps, spend, balance, payment log, scorecard |
| POST /api/pay | record a payment, run the coach, return the nudge |
| POST /api/feedback | record accept / ignore for a nudge |
| POST /api/caps | change a category cap |
| POST /api/reset | clear all payments |

## Agent (3 parts)
1. **Merchant tagger:** fixed map of 11 merchants. Unknown merchant => no category, no nudge (never invents a category).
2. **Cap counter:** spend per category vs cap. Nudge and ask for a choice when a payment would exceed the cap, leave under 25% of it, or is itself 25%+ of the cap.
3. **One-line suggester:** template swap with the estimated saving (0 model calls).

## Rules it follows
- The payment is saved first and always succeeds. The coach runs afterwards and its errors are ignored.
- If a payment would exceed the budget, the user is asked to choose: cheaper swap, pay only what's left, or pay anyway.
- Accept and ignore both count and are stored in the database.

## Scorecard
Accepted swaps (Rs saved) vs extra model tokens. Rules-based suggester => 0 tokens, so nudges never cost more compute than they save.

## Demo script
Press "Play 12-spend demo": 12 payments, 2 accepted swaps, 3 ignored, 7 silent, one over-budget choice, one unknown merchant.
