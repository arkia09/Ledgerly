# Ledgerly

Photograph a page of a paper credit ledger. A local Gemma model (via Ollama)
reads it, you correct mistakes, and the app reports who owes what and for how long.

## Layout
- `extraction/`   Step 1: model prompt, schema, single/batch runners, scoring
- `backend/`      Step 2: Django API (empty for now)
- `frontend/`     Step 3: React app (empty for now)
- `data/pages/`         test photos (gitignored: may contain customer data)
- `data/ground_truth/`  your hand-written correct answers, one JSON per photo
- `data/outputs/`       model outputs per run (gitignored)

## Setup (Windows PowerShell)
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    ollama pull gemma4:e4b

## Step 1 workflow
1. Put photos in `data/pages/` (page01.jpg, page02.jpg, ...).
2. For each, copy `data/ground_truth/_template.json` to `page01.json` and fill in the true rows.
   Set "page_type" to neat, messy or mixed.
3. Edit the layout line in `extraction/prompt.txt` to match your ledger.
4. Try one page:   `cd extraction; python extract.py ..\data\pages\page01.jpg`
5. Run them all:   `python batch.py`
6. Score:          `python score.py --run gemma4_e4b`
Compare prompts or models with `--run NAME` and `--model gemma4:e2b`.

## Backend (Step 2: Django API)

Plain Django, SQLite, no login. Extraction runs synchronously inside the upload request.

### Setup (Windows PowerShell, from the repo root)
    .venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    cd backend
    python manage.py migrate
    python manage.py test
    python manage.py load_demo        # optional: demo customers from data/ground_truth
    python manage.py runserver 8000

API root is `http://localhost:8000/api/`. CORS allows `http://localhost:5173`.
Optional admin: `python manage.py createsuperuser`, then `http://localhost:8000/admin/`.

### Skip the 3-minute model call: LEDGERLY_FAKE_EXTRACT
    $env:LEDGERLY_FAKE_EXTRACT = "1"; python manage.py runserver 8000

With this set, `POST /api/pages/` does not touch Ollama. It returns the saved output from
`data/outputs/v3/` whose filename matches the uploaded file (`page03.jpg` returns `page03.json`),
and falls back to `page01.json` for any other name. Turn it off with
`Remove-Item Env:LEDGERLY_FAKE_EXTRACT`. Real extraction takes about 170 s per page on CPU, so the
frontend needs a long (or no) fetch timeout for the upload call.

### Endpoints
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/pages/` | Upload photo (multipart `image`), run extraction, return rows for review |
| GET | `/api/pages/<id>/` | Same payload again (reload the review screen) |
| POST | `/api/pages/<id>/confirm/` | Save the reviewed rows; 409 if already confirmed |
| GET | `/api/customers/` | All customers, sorted by balance descending |
| GET | `/api/customers/<id>/` | One customer with entries and running balance |
| GET | `/api/reports/balances/` | Who owes what (JSON) |
| GET | `/api/reports/aging/` | Outstanding by age bucket (JSON) |
| GET | `/api/reports/balances.png`, `/api/reports/aging.png` | Matplotlib charts |
| GET | `/api/rules/` | Current "mistakes to avoid" list (debug/demo) |

Money is a JSON number with 2 decimals. Dates are ISO strings. Errors are `{"error": "..."}`.

**POST /api/pages/** returns 201 (abridged):

    {
      "page_id": 7, "status": "extracted", "seconds": 184.7, "model": "gemma4:e4b",
      "image_url": "http://localhost:8000/media/pages/page01.jpg", "page_total": null,
      "extraction_error": null,
      "rows": [{
        "row_index": 0, "raw_text": "01/10 Ramesh Kumar Atta (5Kg) 240",
        "date": "01/10", "name": "Ramesh Kumar", "item": "Atta (5Kg)", "amount": 240.0,
        "type": "credit", "struck_out": false, "confidence": 0.95,
        "date_iso": "2026-10-01", "date_valid": true,
        "suggested_customer": {"id": 1, "name": "Ramesh Kumar", "score": 100.0}
      }],
      "suggestions": [
        {"row_index": null, "field": "struck_out", "code": "check_struck_out", "message": "..."},
        {"row_index": 3, "field": "name", "code": "customer_near_match", "message": "..."}
      ]
    }

`suggestions` are review hints for the UI: `date_unparseable`, `amount_missing`, `type_unknown`,
`name_missing`, `customer_near_match`, plus one page-level reminder that the model never detects
crossed-out rows. If extraction fails the response is 502 with
`{"error": "extraction_failed", "message", "detail", "raw", "page_id"}`; the page and photo are kept.

**POST /api/pages/<id>/confirm/** body:

    {"rows": [{
      "row_index": 0, "date_text": "01/10", "name": "Ramesh Kumar", "item": "Atta (5Kg)",
      "amount": 240, "type": "credit", "struck_out": false,
      "customer_id": null, "create_new_customer": true
    }]}

Response 201: `{"page_id", "status": "confirmed", "entries_created", "corrections_created",
"customers_created", "entries_with_unparsed_date": [entry ids]}`. Invalid input returns 400 with
`details: [{row, field, message}]` and nothing is saved.

Rules for the confirm body:
- `row_index` is the index from the upload response, or `null` for a row the user added.
- Send `date_text` exactly as shown unless the user edited it. It is compared with the model's
  date string, so reformatting it (e.g. to ISO) is recorded as a correction. ISO `YYYY-MM-DD`
  is accepted when the user picks a date.
- `type` must be `credit` or `payment`. `unknown` is rejected: the user has to decide.
- Customer: if `customer_id` is set, that customer is used and its name is the final name.
  If it is `null`, an exact (case-insensitive) name match is reused; otherwise
  `create_new_customer` must be `true` or the row is rejected. Fuzzy matches are only suggestions.
- A date that cannot be parsed is stored as `date: null` with `date_text` kept, and the entry id
  is listed in `entries_with_unparsed_date`.

### Reports
- `balances/`: `{"total_outstanding", "customers": [{"id","name","balance","last_activity"}]}`, balance > 0 only.
- `aging/`: `{"buckets": {"0-30","31-60","61+","unknown"}, "customers": [{"id","name","0-30","31-60","61+","unknown","total"}]}`.
- Balance = credits minus payments, struck-out entries ignored. Aging applies payments to the
  oldest credits first (FIFO) and buckets what is left by age in days. Undated credits are paid
  last and reported as `unknown`.
- Chart caveat: matplotlib cannot shape complex scripts, so some Devanagari names show vowel
  signs in the wrong place in the PNGs. The JSON endpoints are exact.

### How correction feedback works
Every confirm compares your rows with the model's original output (kept untouched in
`Page.extracted_json`) and stores one `Correction` per changed field, plus one `row_deleted`
correction per row you removed. Names and text are compared ignoring case and spacing; amounts
numerically. On the next upload the 5 most recent corrections become short plain-English rules
(e.g. `A name was read as "Honish" but was actually "Harish".`), which are passed to the model as
`extra_rules` ("Mistakes to avoid"). Rules never contain amounts. See them at `GET /api/rules/`.
`prompt.txt` is never edited.

## Frontend (Ledgerly)

The React + TypeScript + Vite app lives in `frontend/`. It uses a warm paper-and-brown theme and talks to the Django API at `http://127.0.0.1:8000/api` by default.

In PowerShell, from the repository root:

```powershell
Set-Location .\frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Open `http://127.0.0.1:5173`. Run the backend in a separate terminal from `backend/` with `python manage.py runserver 8000`. The Vite server is pinned to port 5173 to match Django CORS. See `frontend/README.md` for details.


## Manual customer and transaction management

Ledgerly supports creating customers and recording sales/payments directly in the UI. From Customers, select **Add customer**. Open a customer to record a sale, including the total amount and the amount paid now, or record a later payment separately. The balance and reports refresh after successful saves.
