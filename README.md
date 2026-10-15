# Khata AI

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
