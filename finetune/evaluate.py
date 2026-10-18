"""Run the base model and the fine-tuned model on the held-out pages, then score both.

    python evaluate.py                       # uses data/finetune/run.json written by train.py
    python score.py --run qwen_base  --pages page02,page06      (also run by this script)

Outputs go to data/outputs/qwen_base and data/outputs/qwen_tuned in the same format as
extraction/batch.py, so extraction/score.py works on them unchanged.
"""
import argparse
import asyncio
import json
import subprocess
import sys
import time

import tinker
from tinker import types
from tinker_cookbook.renderers import get_text_content

import common as c


async def run_page(client, renderer, stem, params):
    img = c.load_image(c.find_image(stem))
    prompt = renderer.build_generation_prompt([c.user_message(img)])
    t0 = time.perf_counter()
    r = await client.sample_async(prompt=prompt, num_samples=1, sampling_params=params)
    seconds = time.perf_counter() - t0
    tokens = r.sequences[0].tokens
    text = get_text_content(renderer.parse_response(tokens)[0])
    return text, seconds, len(tokens)


async def run_model(label, client, renderer, model_name, pages, out_dir):
    params = types.SamplingParams(max_tokens=3000, temperature=0.0, stop=renderer.get_stop_sequences())
    results = await asyncio.gather(*(run_page(client, renderer, s, params) for s in pages), return_exceptions=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    for stem, res in zip(pages, results):
        if isinstance(res, Exception):
            rec = {"model": model_name, "error": f"{type(res).__name__}: {res}"}
        else:
            text, seconds, ntok = res
            try:
                rec = {"model": model_name, "seconds": round(seconds, 1), "output_tokens": ntok, "page": c.parse_output(text)}
            except Exception as e:
                rec = {"model": model_name, "seconds": round(seconds, 1), "output_tokens": ntok,
                       "error": f"invalid output: {e}", "raw": text}
        (out_dir / f"{stem}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[{label}] {stem}: {'FAILED ' + rec['error'] if 'error' in rec else str(len(rec['page']['rows'])) + ' rows, ' + str(rec['seconds']) + 's'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None, help="base model (default: the one in run.json, else the default)")
    ap.add_argument("--sampler-path", default=None, help="tinker:// path (default: from run.json)")
    ap.add_argument("--skip-base", action="store_true")
    args = ap.parse_args()

    run = json.loads((c.WORK / "run.json").read_text()) if (c.WORK / "run.json").exists() else {}
    model = args.model or run.get("base_model") or c.DEFAULT_MODEL
    sampler = args.sampler_path or run.get("sampler_path")
    if not sampler:
        raise SystemExit("No fine-tuned model: run train.py first or pass --sampler-path.")
    pages = json.loads((c.WORK / "split.json").read_text())["test"]
    renderer, _ = c.renderer_for(model)
    service = tinker.ServiceClient()

    async def go():
        if not args.skip_base:
            await run_model("base", service.create_sampling_client(base_model=model), renderer,
                            f"{model} (base)", pages, c.OUT_ROOT / "qwen_base")
        await run_model("tuned", service.create_sampling_client(model_path=sampler), renderer,
                        f"{model} (fine-tuned)", pages, c.OUT_ROOT / "qwen_tuned")
    asyncio.run(go())

    score = c.ROOT / "extraction" / "score.py"
    for name in ([] if args.skip_base else ["qwen_base"]) + ["qwen_tuned"]:
        print("\n" + "=" * 70)
        subprocess.run([sys.executable, str(score), "--run", name, "--pages", ",".join(pages)], check=False)


if __name__ == "__main__":
    main()
