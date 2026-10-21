"""CPU LoRA 訓練。預設輸出新資料夾，避免覆蓋原有模型權重。"""
import argparse
import hashlib
import json
import random
import time
from pathlib import Path
from common import BASE_MODEL, REVISION, ROOT, messages, read_jsonl, model_source
import torch
from peft import LoraConfig, PeftModel, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer

def encode(tokenizer, row, limit):
    prefix = tokenizer.apply_chat_template(messages(row["text"]), tokenize=True, add_generation_prompt=True)
    full = tokenizer.apply_chat_template(messages(row["text"], row["expected"]), tokenize=True)
    if full[:len(prefix)] != prefix:
        raise ValueError("chat template prefix mismatch")
    if len(full) > limit:
        raise ValueError(f"training example is too long ({len(full)} > {limit}); do not truncate labels")
    return full, [-100] * len(prefix) + full[len(prefix):]

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--steps", type=int, default=120)
    p.add_argument("--threads", type=int, default=4)
    p.add_argument("--max-length", type=int, default=768)
    p.add_argument("--output", default=str(ROOT / "model_training/artifacts/expense-lora-retrained"))
    p.add_argument("--resume", help="Warm start; optimizer state is not restored")
    p.add_argument("--local-only", action="store_true")
    args = p.parse_args()
    if args.steps < 1 or args.threads < 1:
        p.error("steps and threads must be positive")
    out = Path(args.output)
    if (out / "adapter_model.safetensors").exists():
        p.error("output already contains weights; choose a new --output directory")
    torch.set_num_threads(args.threads)
    torch.manual_seed(42)
    rng = random.Random(42)
    kwargs = {"revision": REVISION, "local_files_only": args.local_only}
    source = model_source()
    tokenizer = AutoTokenizer.from_pretrained(source, **kwargs)
    base = AutoModelForCausalLM.from_pretrained(source, torch_dtype=torch.float32, attn_implementation="eager", **kwargs)
    model = PeftModel.from_pretrained(base, args.resume, is_trainable=True) if args.resume else get_peft_model(base,
        LoraConfig(r=8, lora_alpha=16, lora_dropout=0.05, target_modules=["q_proj", "v_proj"], task_type="CAUSAL_LM", bias="none"))
    model.config.use_cache = False
    model.peft_config["default"].base_model_name_or_path = BASE_MODEL
    model.peft_config["default"].revision = REVISION
    model.print_trainable_parameters()
    path = ROOT / "model_training/data/train.jsonl"
    rows = read_jsonl(path)
    rng.shuffle(rows)
    encoded = [encode(tokenizer, row, args.max_length) for row in rows]
    optimizer = torch.optim.AdamW((v for v in model.parameters() if v.requires_grad), lr=3e-4)
    out.mkdir(parents=True, exist_ok=True)
    initial = {n: v.detach().clone() for n, v in model.named_parameters() if v.requires_grad}
    model.train()
    history = []
    started = time.monotonic()
    for step in range(args.steps):
        ids, labels = encoded[step % len(encoded)]
        optimizer.zero_grad(set_to_none=True)
        loss = model(input_ids=torch.tensor([ids]), labels=torch.tensor([labels])).loss
        if not torch.isfinite(loss):
            raise RuntimeError("non-finite loss")
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        history.append({"step": step + 1, "loss": round(loss.item(), 6), "seconds": round(time.monotonic() - started, 2)})
        if step == 0 or (step + 1) % 5 == 0:
            print(json.dumps(history[-1]), flush=True)
        if (step + 1) % 20 == 0 or step + 1 == args.steps:
            # 只訓練 q_proj/v_proj，未修改詞表或 embedding；避免 PEFT 儲存時探測網路。
            model.save_pretrained(out, save_embedding_layers=False)
            tokenizer.save_pretrained(out)
            report = {"base_model": BASE_MODEL, "revision": REVISION, "method": "LoRA (not QLoRA)",
                "device": "cpu", "steps": step + 1, "seed": 42, "learning_rate": 3e-4, "rank": 8,
                "targets": ["q_proj", "v_proj"], "changed_parameter_tensors": sum(not torch.equal(initial[n], v.detach()) for n, v in model.named_parameters() if v.requires_grad),
                "trainable_parameters": sum(v.numel() for v in model.parameters() if v.requires_grad),
                "training_data_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "history": history, "resumed_from": args.resume}
            (out / "training_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved adapter: {out}", flush=True)

if __name__ == "__main__":
    main()
