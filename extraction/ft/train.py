"""Fine-tune a vision model on Tinker (LoRA, supervised) to read ledger pages.

    export TINKER_API_KEY=...            (and set up billing in the Tinker console)
    python ft/train.py --dry-run         # build + render the data, no network training, no cost
    python ft/train.py                   # train; writes ft/last_model.json

Costs money on Tinker. Start with the defaults (small LoRA, a few epochs) and look at the loss.
"""
import argparse
import json
import random
import time

from ftcommon import BASE_MODEL, MODEL_FILE
from dataset import TEST_PAGES, build_examples


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=BASE_MODEL)
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--augment", type=int, default=3, help="extra augmented copies per page")
    ap.add_argument("--from-db", action="store_true", help="also train on pages confirmed in the app")
    ap.add_argument("--dry-run", action="store_true", help="build and render examples only")
    args = ap.parse_args()

    import tinker
    from tinker_cookbook import model_info, renderers
    from tinker_cookbook.image_processing_utils import get_image_processor
    from tinker_cookbook.supervised.common import compute_mean_nll
    from tinker_cookbook.supervised.data import conversation_to_datum
    from tinker_cookbook.tokenizer_utils import get_tokenizer

    renderer_name = model_info.get_recommended_renderer_name(args.model)
    renderer = renderers.get_renderer(renderer_name, get_tokenizer(args.model),
                                      get_image_processor(args.model))
    examples = build_examples(args.augment, args.from_db)
    data = [conversation_to_datum(e["messages"], renderer, 16384,
                                  renderers.TrainOnWhat.LAST_ASSISTANT_MESSAGE) for e in examples]
    tokens = sum(d.model_input.length for d in data)
    print(f"{len(data)} examples, {tokens:,} tokens/epoch, renderer={renderer_name}, "
          f"held out: {', '.join(TEST_PAGES)}")
    if args.dry_run:
        return

    service = tinker.ServiceClient()
    trainer = service.create_lora_training_client(base_model=args.model, rank=args.rank)
    steps_per_epoch = max(1, len(data) // args.batch_size)
    total = steps_per_epoch * args.epochs
    rng, step, started = random.Random(0), 0, time.time()
    for epoch in range(args.epochs):
        rng.shuffle(data)
        for b in range(steps_per_epoch):
            batch = data[b * args.batch_size:(b + 1) * args.batch_size]
            lr = args.lr * max(0.1, 1 - step / total)            # linear decay
            fwd = trainer.forward_backward(batch, loss_fn="cross_entropy")
            opt = trainer.optim_step(tinker.AdamParams(learning_rate=lr, beta1=0.9, beta2=0.95, eps=1e-8))
            result = fwd.result(); opt.result()
            nll = compute_mean_nll([o["logprobs"] for o in result.loss_fn_outputs],
                                   [d.loss_fn_inputs["weights"] for d in batch])
            print(f"epoch {epoch + 1}/{args.epochs} step {step + 1}/{total} "
                  f"loss/token {nll:.4f} lr {lr:.2e}")
            step += 1

    saved = trainer.save_weights_for_sampler(name="ledgerly-ft").result()
    info = {"model_path": saved.path, "base_model": args.model, "renderer": renderer_name,
            "epochs": args.epochs, "examples": len(data), "train_seconds": round(time.time() - started),
            "held_out": TEST_PAGES}
    MODEL_FILE.write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(f"Saved. {MODEL_FILE.name}: {info['model_path']}")


if __name__ == "__main__":
    main()
