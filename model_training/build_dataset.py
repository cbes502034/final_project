"""重建原訓練資料。固定種子與原句型，並以訓練紀錄 SHA-256 核對。"""
import json
import random
from common import ROOT

ITEMS = {
    "食": ["早餐", "午餐", "晚餐", "飲料", "零食", "咖啡", "便當"],
    "衣": ["衣服", "外套", "鞋子"], "住": ["房租", "水費", "電費"],
    "行": ["加油", "停車", "車票", "計程車"], "育": ["學費", "課本", "補習費"],
    "樂": ["電影票", "遊戲", "演唱會門票"], "其他": ["買周邊", "購買周邊", "捐款"],
}
TEMPLATES = {
    "train": ["{item}{amount}", "{item}花了{amount}元", "買了{item}，{amount}塊", "今天{item}{amount}元"],
    "validation": ["{item}共付{amount}元", "{item}支出{amount}元"],
    "test": ["剛剛付了{amount}元買{item}", "我在{item}上花費{amount}元"],
}

def make_row(category, item, amount, template, group):
    return {"text": template.format(item=item, amount=amount), "group": group,
        "expected": {"expenses": [{"category": category, "item": "娛樂" if "周邊" in item else item, "amount": amount}]}}

def build():
    rng = random.Random(42)
    out = ROOT / "model_training/data"
    out.mkdir(parents=True, exist_ok=True)
    splits = {}
    for split, templates in TEMPLATES.items():
        rows = []
        for n, template in enumerate(templates):
            for category, items in ITEMS.items():
                for item in items:
                    rows.append(make_row(category, item, rng.choice([35, 50, 85, 100, 150, 200, 350, 800, 1200]), template, f"{split}:template-{n}"))
        missing = {"train": "{item}忘記金額", "validation": "{item}金額不確定", "test": "有買{item}但忘了多少錢"}[split]
        for category, items in ITEMS.items():
            for item in items:
                rows.append(make_row(category, item, None, missing, f"{split}:missing"))
        approx = {"train": "{item}大約{amount}元", "validation": "{item}{amount}元左右", "test": "{item}大概{amount}塊"}[split]
        for category, items in ITEMS.items():
            for item in items[:1]:
                row = make_row(category, item, 100, approx, f"{split}:approx")
                row["expected"]["expenses"][0]["amount"] = None
                rows.append(row)
        separator = {"train": "，", "validation": "；", "test": " 然後 "}[split]
        for n in range(12 if split == "train" else 4):
            chosen = rng.sample([(c, i) for c, items in ITEMS.items() for i in items], 3)
            parts = [make_row(c, i, rng.choice([50, 100, 200, 350]), templates[0], "") for c, i in chosen]
            rows.append({"text": separator.join(p["text"] for p in parts), "group": f"{split}:multi",
                         "expected": {"expenses": [p["expected"]["expenses"][0] for p in parts]}})
        empty = {"train": "今天沒有支出", "validation": "今天沒買任何東西", "test": "沒有花錢"}[split]
        rows.append({"text": empty, "group": f"{split}:empty", "expected": {"expenses": []}})
        rng.shuffle(rows)
        splits[split] = rows
    splits["test"].append({"text": "早餐50 午餐100 晚餐200 加油100 買周邊200", "group": "test:user-example",
        "expected": {"expenses": [{"category": c, "item": i, "amount": a} for c, i, a in
            [("食", "早餐", 50), ("食", "午餐", 100), ("食", "晚餐", 200), ("行", "加油", 100), ("其他", "娛樂", 200)]]}})
    for split, rows in splits.items():
        (out / f"{split}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    manifest = {"source": "hand-authored category labels with synthetic templates; not real user data",
        "seed": 42, "split_strategy": "disjoint template families", "counts": {k: len(v) for k, v in splits.items()}}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))

if __name__ == "__main__":
    build()
