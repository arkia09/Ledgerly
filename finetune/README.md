# Fine-tuning a vision model on Tinker

Goal: show a measurable improvement from fine-tuning a vision-language model (Qwen3-VL) on your own
ledger pages, compared with the same model before tuning. Compare against local Gemma too, since
`extraction/score.py` reads every run in the same format.

## Before you start
- Tinker is a hosted, paid service. Check pricing and any hackathon credits first.
- **Privacy:** training and evaluation upload your ledger photos to Tinker. The app itself never calls
  Tinker; this folder is a separate offline workflow. Use photos you are happy to upload.
- Needs internet (the tokenizer and image processor are fetched from Hugging Face).

## Setup
    pip install -r finetune/requirements.txt
    export TINKER_API_KEY=...            # PowerShell: $env:TINKER_API_KEY="..."

## Run
    cd finetune
    python -m unittest test_data         # offline sanity check
    python prepare_data.py               # builds data/finetune/ (no key needed)
    python train.py                      # LoRA fine-tune on Tinker; writes data/finetune/run.json
    python evaluate.py                   # base vs tuned on held-out pages, then scores both

`prepare_data.py` holds out `page02,page06` for testing (`--test` to change). Training pages are never
scored. Each is augmented into 16 photo variants (tilt, crop, light, blur, JPEG noise).
`evaluate.py` writes `data/outputs/qwen_base` and `data/outputs/qwen_tuned`; you can also run
`python extraction/score.py --run gemma4_e4b --pages page02,page06` for the local Gemma baseline.
Compare accuracy, `output_tokens`, and seconds per page.

## More labelled pages = a trustworthy result
Four training pages is very little. The easy way to add more: photograph a page, upload it in Ledgerly,
fix the rows in the review screen, confirm, then run

    cd backend && python manage.py export_training_data

which writes `data/pages/app_<id>.jpg` and `data/ground_truth/app_<id>.json`. Re-run `prepare_data.py`.
Only export pages where the names you confirmed match what is written on the page (merging "Ramesh" into
"Ramesh Kumar" makes the label differ from the photo). Aim for 20+ pages.

## Choices you can change
- Model: `--model Qwen/Qwen3.5-9B` (cheaper) or another vision model in the cookbook. The renderer is chosen
  automatically; the `*_disable_thinking` variant is preferred.
- `--epochs`, `--batch-size`, `--rank`, `--lr` on `train.py`. Watch the train loss; if it keeps falling but
  test accuracy does not improve, you are overfitting four pages.
- The tuned model outputs compact JSON without `confidence`; `common.parse_output` fills `raw_text` and a
  fixed confidence of 1.0 so the result fits the app's schema.

## Status
`prepare_data.py`, `common.py` and the export command are tested. `train.py` and `evaluate.py` follow the
Tinker SDK and cookbook signatures (tinker 0.34, tinker-cookbook 0.5.7) but have NOT been run against the
real service, because they need your API key and internet access to Hugging Face.
