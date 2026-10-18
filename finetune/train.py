"""LoRA fine-tune a vision-language model on Tinker to read ledger pages.

    export TINKER_API_KEY=...        (PowerShell: $env:TINKER_API_KEY="...")
    python prepare_data.py
    python train.py                  # ~30 small steps; prints loss; saves a sampler checkpoint
    python train.py --model Qwen/Qwen3.5-9B --epochs 4

Writes data/finetune/run.json with the tinker:// path that evaluate.py uses.
"""
import argparse
import json
import random
import time

import tinker
from tinker_cookbook import checkpoint_utils, renderers
from tinker_cookbook.hyperparam_utils import get_lr
from tinker_cookbook.supervised.common import compute_mean_nll, datum_from_model_input_weights

import common as c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=c.DEFAULT_MODEL)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--rank", type=int, default=32, help="LoRA rank")
    ap.add_argument("--lr", type=float, default=None, help="default: cookbook's recommendation for this model")
    ap.add_argument("--max-length", type=int, default=8192)
    args = ap.parse_args()

    rows = [json.loads(l) for l in (c.WORK / "train.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    if not rows:
        raise SystemExit("data/finetune/train.jsonl is empty. Run prepare_data.py first.")

    renderer, renderer_name = c.renderer_for(args.model)
    lr = args.lr
    if lr is None:
        try:
            lr = get_lr(args.model, is_lora=True)
        except Exception as e:  # needs to read the model config from Hugging Face
            lr = 1e-4
            print(f"(could not look up a recommended LR: {e}; using {lr})")
    print(f"model={args.model} renderer={renderer_name} examples={len(rows)} lr={lr:.2e} rank={args.rank}")

    from PIL import Image
    datums = []
    for r in rows:
        img = Image.open(c.WORK / "train" / r["image"]).convert("RGB")
        messages = [c.user_message(img), renderers.Message(role="assistant", content=r["target"])]
        model_input, weights = renderer.build_supervised_example(
            messages, train_on_what=renderers.TrainOnWhat.LAST_ASSISTANT_MESSAGE)
        datums.append(datum_from_model_input_weights(model_input, weights, max_length=args.max_length))

    service = tinker.ServiceClient()
    client = service.create_lora_training_client(base_model=args.model, rank=args.rank)

    steps_per_epoch = max(1, len(datums) // args.batch_size)
    total = steps_per_epoch * args.epochs
    rng, step, t0 = random.Random(0), 0, time.time()
    for epoch in range(args.epochs):
        rng.shuffle(datums)
        for b in range(steps_per_epoch):
            batch = datums[b * args.batch_size:(b + 1) * args.batch_size]
            adam = tinker.AdamParams(learning_rate=lr * max(0.05, 1 - step / total), beta1=0.9, beta2=0.95, eps=1e-8)
            fb = client.forward_backward(batch, loss_fn="cross_entropy")
            opt = client.optim_step(adam)
            res = fb.result(); opt.result()
            nll = compute_mean_nll([x["logprobs"] for x in res.loss_fn_outputs],
                                   [d.loss_fn_inputs["weights"] for d in batch])
            step += 1
            print(f"epoch {epoch + 1}/{args.epochs} step {step}/{total}  train loss {nll:.4f}", flush=True)

    paths = checkpoint_utils.save_checkpoint(
        training_client=client, name="ledgerly-final", log_path=str(c.WORK / "logs"),
        loop_state={"step": step}, kind="both")
    info = {"base_model": args.model, "renderer": renderer_name, "sampler_path": paths["sampler_path"],
            "state_path": paths.get("state_path"), "steps": step, "examples": len(rows),
            "train_seconds": round(time.time() - t0, 1)}
    (c.WORK / "run.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    print("\nSaved:", json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
