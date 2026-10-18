# Fine-tuning a ledger reader on Tinker

Goal: show that a model fine-tuned on *your* ledger pages reads them better than the same model
untouched. Base model: `Qwen/Qwen3-VL-30B-A3B-Instruct` (override with `TINKER_BASE_MODEL`).

## Setup
    pip install -r extraction/ft/requirements.txt
    export TINKER_API_KEY=...        # PowerShell: $env:TINKER_API_KEY = "..."
Create the key and set up billing in the Tinker console. **Training and sampling cost money.**

## Steps (run from `extraction/`)
    python ft/dataset.py             # how many training examples, which pages are held out
    python ft/train.py --dry-run     # renders everything with the real tokenizer, no training, no cost
    python ft/train.py               # trains, writes ft/last_model.json
    python ft/evaluate.py            # base vs fine-tuned on held-out pages, via score.py
    python ft/compare.py             # builds data/compare.html: photo + truth + every model, side by side

Held-out pages (`TEST_PAGES` in `dataset.py`: page02, page04, page06) are never trained on.
Never score on pages the model trained on; the improvement would be fake.

## Side-by-side page for the demo
`python ft/compare.py` reads the saved outputs (no Tinker key, no network, no cost) and writes
`data/compare.html`: a scoreboard tab plus one tab per held-out page, showing your ground truth next to
Gemma, base Qwen and fine-tuned Qwen row by row. Wrong fields are red with the correct value underneath.
Options: `--pages page04`, `--runs gemma4_e4b,tinker_ft`, `--out path.html`, `--no-open`.
It uses score.py's own matching, so its numbers equal `python score.py --run <name>`.

## More data = the whole game
Three labelled training pages is very little. Two ways to add more:
1. Photograph and label more pages (`data/ground_truth/`, `data/pages/`).
2. Review pages in the app as usual, then `python ft/train.py --from-db`. Confirmed pages carry
   your corrections, so using the app produces training data.

## Using the result in the app (opt-in)
    export LEDGERLY_EXTRACTOR=tinker     # default is ollama (local)
**Privacy:** with `tinker`, each uploaded photo is sent to Tinker's cloud. Leave it unset to keep
everything on this computer.

## Files
`ftcommon.py` shared prompt/preprocessing/parsing · `dataset.py` training pairs + augmentation ·
`train.py` LoRA SFT loop · `sampler.py` inference (base or fine-tuned) · `evaluate.py` comparison · `compare.py` HTML side-by-side
