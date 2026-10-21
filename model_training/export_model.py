"""匯出完整模型到新資料夾，不覆蓋先前保存的完整模型。"""
import argparse
from pathlib import Path
from common import ROOT
from inference import ExpenseModel

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--adapter", default=str(ROOT / "model_training/artifacts/expense-lora"))
    p.add_argument("--output", default=str(ROOT / "model_training/artifacts/expense-merged-restored"))
    args = p.parse_args()
    out = Path(args.output)
    if (out / "config.json").exists():
        p.error("output already contains a model; choose a new directory")
    engine = ExpenseModel(args.adapter)
    merged = engine.model.merge_and_unload()
    merged.save_pretrained(out, safe_serialization=True)
    engine.tokenizer.save_pretrained(out)
    print(f"Saved merged model: {out}")

if __name__ == "__main__":
    main()
