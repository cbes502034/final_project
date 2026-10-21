"""單獨測試模型：預設回驗證後 JSON，--raw 可查看模型原始答案。"""
import argparse
import json
import os
from pathlib import Path
from common import BASE_MODEL, REVISION, ROOT, messages, model_source, strict_json
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "local-model-inference-only-not-an-auth-server")
from app.services.llm.expenses import validate_expenses

class ExpenseModel:
    def __init__(self, adapter=None, threads=4, merged=None):
        torch.set_num_threads(threads)
        torch.manual_seed(42)
        source = merged or model_source()
        self.tokenizer = AutoTokenizer.from_pretrained(source, revision=REVISION, local_files_only=True)
        base = AutoModelForCausalLM.from_pretrained(source, revision=REVISION, local_files_only=True,
            torch_dtype=torch.float32, attn_implementation="eager")
        self.model = PeftModel.from_pretrained(base, adapter) if adapter and not merged else base
        self.model.eval()
        self.model.config.use_cache = True
        self.model.generation_config.temperature = 1.0
        self.model.generation_config.top_p = 1.0
        self.model.generation_config.top_k = 50

    @torch.inference_mode()
    def generate(self, text):
        prompt = self.tokenizer.apply_chat_template(messages(text), tokenize=False, add_generation_prompt=True)
        inputs = self.tokenizer(prompt, return_tensors="pt")
        ids = self.model.generate(**inputs, max_new_tokens=512, do_sample=False, pad_token_id=self.tokenizer.eos_token_id)
        return self.tokenizer.decode(ids[0, inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()

    def parse(self, text):
        return validate_expenses(strict_json(self.generate(text)), text)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("text")
    p.add_argument("--adapter", default=str(ROOT / "model_training/artifacts/expense-lora"))
    p.add_argument("--base-only", action="store_true")
    p.add_argument("--merged")
    p.add_argument("--raw", action="store_true", help="Show the unmodified model answer")
    args = p.parse_args()
    if args.base_only and args.merged:
        p.error("base-only and merged cannot be combined")
    engine = ExpenseModel(None if args.base_only else Path(args.adapter), merged=args.merged)
    print(engine.generate(args.text) if args.raw else json.dumps(engine.parse(args.text), ensure_ascii=False, allow_nan=False))

if __name__ == "__main__":
    main()
