"""
模型呼叫層、記帳解析的後處理、財務建議的數字檢查。**不會真的打任何模型**（conftest.py 先把設定清空了）。

領域：記帳、數字

    OpenAI 相容   用 httpx.MockTransport 假裝成服務，看送出去的 body、讀回來的 tool_calls
    Claude        把 anthropic.Anthropic 換成假的，看送進 SDK 的參數
"""

import json
import os
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production-at-least-32-bytes-long")

import httpx  # noqa: E402
import pytest  # noqa: E402

from app.services.llm import advice, client, parse  # noqa: E402
from app.toolkit.config import CLAUDE_DEFAULT, Settings, settings  # noqa: E402

TODAY = "2026-10-02"
CATS = [{"id": "1", "name": "餐飲", "kind": "expense"}, {"id": "2", "name": "交通", "kind": "expense"},
        {"id": "9", "name": "薪資", "kind": "income"}]


def _openai(monkeypatch, *replies):
    """依序回 replies（(狀態碼, body)）的假服務；回傳 (client, 送出去的每一個 body)。"""
    monkeypatch.setattr(settings, "model_base_url", "http://model.test")
    sent, queue = [], list(replies)

    def handler(request):
        sent.append(json.loads(request.content))
        status, body = queue.pop(0)
        return httpx.Response(status, json=body) if isinstance(body, dict) else httpx.Response(status, text=body)

    return httpx.Client(transport=httpx.MockTransport(handler)), sent


def _tool_reply(args):
    return (200, {"choices": [{"message": {"content": None, "tool_calls": [
        {"type": "function", "function": {"name": "record_transactions", "arguments": json.dumps(args)}}]}}]})


# ===========================================================================
# OpenAI 相容
# ===========================================================================
def test_openai_工具呼叫_送_tools_拿回_arguments(monkeypatch):
    http, sent = _openai(monkeypatch, _tool_reply({"items": []}))
    out = client.complete_json("早餐55", system="s", tool=parse.RECORD_TOOL, client=http)
    assert out == {"items": []}
    body = sent[0]
    assert body["tool_choice"] == "required"
    assert body["tools"][0]["function"]["name"] == "record_transactions"
    assert body["tools"][0]["function"]["parameters"] == parse.RECORD_TOOL["input_schema"]
    assert body["messages"][0] == {"role": "system", "content": "s"}


def test_openai_服務不用工具_改回文字_JSON_也接得住(monkeypatch):
    http, _ = _openai(monkeypatch, (200, {"choices": [{"message": {"content": '```json\n{"items": [1]}\n```'}}]}))
    assert client.complete_json("x", tool=parse.RECORD_TOOL, client=http) == {"items": [1]}


def test_openai_schema_用_response_format(monkeypatch):
    http, sent = _openai(monkeypatch, (200, {"choices": [{"message": {"content": '{"advices": []}'}}]}))
    assert client.complete_json("x", schema=advice.ADVICE_SCHEMA, client=http) == {"advices": []}
    fmt = sent[0]["response_format"]
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["schema"] == advice.ADVICE_SCHEMA


def test_openai_回_400_說不收某個參數_換掉再送(monkeypatch):
    http, sent = _openai(
        monkeypatch,
        (400, "Unsupported parameter: 'max_tokens' is not supported with this model. Use 'max_completion_tokens'."),
        (400, "Unsupported value: 'temperature' does not support 0.1 with this model."),
        _tool_reply({"items": []}),
    )
    assert client.complete_json("x", tool=parse.RECORD_TOOL, max_tokens=1024, client=http) == {"items": []}
    assert "max_tokens" in sent[0] and "temperature" in sent[0]
    assert "max_tokens" not in sent[1] and sent[1]["max_completion_tokens"] == 4096
    assert "temperature" not in sent[2]


def test_openai_400_但看不出是哪個參數_就丟_ModelError(monkeypatch):
    http, sent = _openai(monkeypatch, (400, "bad request"))
    with pytest.raises(client.ModelError):
        client.complete_json("x", client=http)
    assert len(sent) == 1


def test_建議可以用另一組設定_每一欄留空就沿用記帳那一組(monkeypatch):
    monkeypatch.setattr(settings, "model_base_url", "http://parse.test")
    monkeypatch.setattr(settings, "model_name", "qwen")
    assert client.model_name("advice") == "qwen"
    monkeypatch.setattr(settings, "advice_base_url", "http://advice.test")
    monkeypatch.setattr(settings, "advice_model_name", "gpt-x")
    seen = []
    http = httpx.Client(transport=httpx.MockTransport(
        lambda r: seen.append(str(r.url)) or httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})))
    client.complete_json("x", purpose="advice", client=http)
    client.complete_json("x", client=http)
    assert seen == ["http://advice.test/v1/chat/completions", "http://parse.test/v1/chat/completions"]
    assert client.model_name("advice") == "gpt-x" and client.model_name() == "qwen"


# ===========================================================================
# Claude
# ===========================================================================
@pytest.fixture()
def claude(monkeypatch):
    anthropic = pytest.importorskip("anthropic")
    box = {"reply": None, "calls": [], "init": []}

    class Messages:
        def create(self, **kwargs):
            box["calls"].append(kwargs)
            return box["reply"]

    class FakeSDK:
        def __init__(self, **kwargs):
            box["init"].append(kwargs)
            self.messages = Messages()
            self.beta = SimpleNamespace(messages=Messages())

    monkeypatch.setattr(anthropic, "Anthropic", FakeSDK)
    monkeypatch.setattr(settings, "model_provider", "anthropic")
    monkeypatch.setattr(settings, "model_api_key", "sk-ant-test")
    return box


def test_claude_沒改模型名稱就用預設那一顆_工具是_strict(claude):
    claude["reply"] = SimpleNamespace(stop_reason="tool_use", content=[
        SimpleNamespace(type="text", text="好"),
        SimpleNamespace(type="tool_use", name="record_transactions", input={"items": []})])
    assert client.is_configured() and client.model_name() == CLAUDE_DEFAULT
    assert client.complete_json("早餐55", system="s", tool=parse.RECORD_TOOL) == {"items": []}
    call = claude["calls"][0]
    assert call["model"] == CLAUDE_DEFAULT and call["system"] == "s"
    assert call["tools"][0]["strict"] is True
    assert call["tools"][0]["input_schema"] == parse.RECORD_TOOL["input_schema"]
    assert "record_transactions 工具" in call["messages"][0]["content"]
    assert call["extra_body"]["output_config"] == {"effort": "low"}
    assert call["extra_body"]["fallbacks"] == "default" and call["betas"]
    assert claude["init"][0]["api_key"] == "sk-ant-test"


def test_claude_schema_走結構化輸出_文字就是_JSON(claude):
    claude["reply"] = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text='{"advices": []}')])
    assert client.complete_json("x", schema=advice.ADVICE_SCHEMA, purpose="advice") == {"advices": []}
    fmt = claude["calls"][0]["extra_body"]["output_config"]
    assert fmt["format"] == {"type": "json_schema", "schema": advice.ADVICE_SCHEMA}
    assert fmt["effort"] == "medium"                    # 建議用 ADVICE_EFFORT


def test_claude_婉拒要丟_ModelError(claude):
    claude["reply"] = SimpleNamespace(stop_reason="refusal", content=[])
    with pytest.raises(client.ModelError):
        client.complete_json("x", tool=parse.RECORD_TOOL)


def test_claude_沒填金鑰就是沒設定(claude, monkeypatch):
    monkeypatch.setattr(settings, "model_api_key", "")
    assert not client.is_configured()
    assert client.complete("x") is None and claude["calls"] == []


def test_設定檔_用_Claude_卻沒改模型名稱_記成預設那一顆():
    s = Settings(database_url="sqlite://", jwt_secret="x" * 40, model_provider="anthropic", model_api_key="k",
                 _env_file=None)
    assert s.model_name == CLAUDE_DEFAULT
    s = Settings(database_url="sqlite://", jwt_secret="x" * 40, advice_provider="anthropic", _env_file=None)
    assert s.advice_model_name == CLAUDE_DEFAULT and s.model_name == "qwen2.5-1.5b-fambudget"


# ===========================================================================
# 工具的 schema：strict 模式的要求
# ===========================================================================
def _objects(schema):
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            yield schema
        for v in schema.values():
            yield from _objects(v)
    elif isinstance(schema, list):
        for v in schema:
            yield from _objects(v)


@pytest.mark.parametrize("schema", [parse.RECORD_TOOL["input_schema"], advice.ADVICE_SCHEMA])
def test_schema_每一層物件都列滿_required_而且不收多的欄位(schema):
    """Claude 的 strict 工具、OpenAI 的 strict 結構化輸出都要求這兩點，少一個就整個請求被拒。"""
    for obj in _objects(schema):
        assert obj.get("additionalProperties") is False
        assert sorted(obj["required"]) == sorted(obj["properties"])


# ===========================================================================
# 記帳解析的後處理
# ===========================================================================
def _raw(**kw):
    base = {"span": "早餐55", "date": TODAY, "amount": 55, "kind": "expense", "cat": "1", "merchant": "",
            "note": "早餐", "conf": {"date": 0.9, "amount": 0.9, "kind": 0.9, "cat": 0.9}}
    base.update(kw)
    return base


def test_span_裡有時間詞_日期以換算為準():
    items = parse.postprocess({"items": [_raw(span="昨天早餐55"), _raw(span="上禮拜三加油800", amount=800, cat="2")]},
                              CATS, TODAY)
    assert [i["date"] for i in items] == ["2026-10-01", "2026-09-23"]
    assert items[0]["missing"] == [] and items[0]["conf"]["date"] >= 0.9


def test_模型沒給日期_但_span_講了_一樣補得回來():
    item = parse.postprocess({"items": [_raw(span="前天午餐120", date=None, amount=120)]}, CATS, TODAY)[0]
    assert item["date"] == "2026-09-30" and "date" not in item["missing"]


def test_金額跟原句的數字對不上_信心度壓低():
    ok, bad = parse.postprocess({"items": [_raw(), _raw(amount=550)]}, CATS, TODAY)
    assert ok["conf"]["amount"] == 0.9 and bad["conf"]["amount"] == 0.5
    cn = parse.postprocess({"items": [_raw(span="早餐五十五", amount=55)]}, CATS, TODAY)[0]
    assert cn["conf"]["amount"] == 0.9                  # 原句沒有阿拉伯數字就不比


def test_這一段沒講日期_沿用同一段話前面講的():
    """線上評測唯一錯的一題：「昨天停車費100，晚餐350」，模型把晚餐記成今天。"""
    text = "昨天停車費100，晚餐350"
    a, b = parse.postprocess({"items": [_raw(span="昨天停車費100", amount=100, cat="2"),
                                        _raw(span="晚餐350", amount=350)]}, CATS, TODAY, text)
    assert a["date"] == b["date"] == "2026-10-01" and 0.7 <= b["conf"]["date"] <= 0.8
    # 兩段都講了日期：各用各的；都沒講：就是今天
    x, y = parse.postprocess({"items": [_raw(span="昨天搭高鐵1490", amount=1490, cat="2"),
                                        _raw(span="今天計程車250", amount=250, cat="2")]}, CATS, TODAY)
    assert (x["date"], y["date"]) == ("2026-10-01", TODAY)
    p, q = parse.postprocess({"items": [_raw(), _raw(span="午餐120", amount=120)]}, CATS, TODAY)
    assert p["date"] == q["date"] == TODAY


def test_萬_也算原句寫的數字_不要誤報():
    """「房租 1.2 萬」→ 12000 是對的，以前被當成抄錯、信心度壓到 0.5。"""
    item = parse.postprocess({"items": [_raw(span="房租 1.2 萬", amount=12000, cat="3")]}, CATS, TODAY)[0]
    assert item["conf"]["amount"] == 0.9
    wrong = parse.postprocess({"items": [_raw(span="房租 1.2 萬", amount=1200, cat="3")]}, CATS, TODAY)[0]
    assert wrong["conf"]["amount"] == 0.5
    assert parse.written_amounts("年終 8 萬") == {80000.0}


def test_這一段沒有任何數字_金額一定是空的():
    item = parse.postprocess({"items": [_raw(span="晚上加油", amount=1000, cat="2")]}, CATS, TODAY, "晚上加油")[0]
    assert item["amount"] is None and "amount" in item["missing"] and item["conf"]["amount"] == 0
    cn = parse.postprocess({"items": [_raw(span="早餐三十五", amount=35)]}, CATS, TODAY)[0]
    assert cn["amount"] == 35                            # 中文數字也算有講


def test_店家與_span_要真的出現在原句裡():
    text = "全家一起吃火鍋 1800"
    item = parse.postprocess({"items": [_raw(span=text, amount=1800, merchant="全家", note="火鍋")]},
                             CATS, TODAY, text)[0]
    assert item["merchant"] == "" and item["hint"] == ""         # 全家人，不是便利商店
    store = parse.postprocess({"items": [_raw(span="全家飯糰35", amount=35, merchant="全家")]}, CATS, TODAY,
                              "全家飯糰35")[0]
    assert store["merchant"] == "全家"
    made_up = parse.postprocess({"items": [_raw(span="中午麥當勞 159", amount=159, merchant="星巴克")]},
                                CATS, TODAY, "中午麥當勞 159")[0]
    assert made_up["merchant"] == ""
    ghost = parse.postprocess({"items": [_raw(), _raw(span="晚餐200", amount=200)]}, CATS, TODAY, "早餐55")[1]
    assert ghost["hint"] == parse.INVENTED_HINT and max(ghost["conf"].values()) <= parse.INVENTED_CONF
    assert parse.postprocess({"items": [_raw()]}, CATS, TODAY, "早餐55")[0]["hint"] == ""


def test_備註填成分類名稱_清掉():
    item = parse.postprocess({"items": [_raw(span="中午麥當勞 159", amount=159, merchant="麥當勞", note="餐飲")]},
                             CATS, TODAY)[0]
    assert item["note"] == "" and item["merchant"] == "麥當勞"


def test_分類習慣_只在收支對得上時套用_不碰金額():
    habit = parse.habits([({"note": "文具"}, {"cat": "2"}), ({"merchant": "全家"}, {"cat": "1"}),
                          ({"note": "薪水"}, {"cat": "9"})])
    items = parse.postprocess({"items": [_raw(span="文具150", amount=150, note="文具"),
                                         _raw(span="全家飯糰35", amount=35, merchant="全家", note="飯糰", cat="2"),
                                         _raw(span="早餐55")]}, CATS, TODAY, "文具150，全家飯糰35，早餐55")
    out = parse.apply_habits(items, habit, CATS)
    assert [i["cat"] for i in out] == ["2", "1", "1"] and [i["amount"] for i in out] == [150, 35, 55]
    assert "交通" in out[0]["hint"] and out[2]["hint"] == ""
    # 收入的習慣不會套到支出上
    pay = parse.apply_habits([{**_raw(span="薪水?", note="薪水"), "conf": {"cat": 0.5}, "missing": [], "hint": ""}],
                             habit, CATS)[0]
    assert pay["cat"] == "1"


def test_收入的分類配支出_分類放進_missing():
    item = parse.postprocess({"items": [_raw(cat="9")]}, CATS, TODAY)[0]
    assert item["cat"] is None and item["missing"] == ["cat"]


def test_prompt_有今天_分類清單_與範例():
    system, prompt = parse.build_prompt("午餐120", CATS, TODAY)
    assert "今天是 2026-10-02" in system and "1：餐飲（支出）" in system and "9：薪資（收入）" in system
    assert prompt.endswith("輸入：午餐120\n輸出：") and "範例輸出：" in prompt


# ===========================================================================
# 財務建議：數字要有出處
# ===========================================================================
NUMBERS = {"period": "2026-10", "income": 20000.0, "expense": 8600.0, "count": 2,
           "savings": {"goal": 10000.0, "allowance": 10000.0, "used": 8600.0, "left": 1400.0, "ratio": 0.86,
                       "level": "near", "shortfall": 0, "actual": 11400.0},
           "byCat": [{"name": "餐飲", "amount": 6000.0}, {"name": "交通", "amount": 2600.0}], "monthly": []}


@pytest.mark.parametrize("text", [
    "支出 8,600 ÷ 可以花 10,000",
    "已經用掉 86%",
    "支出佔收入 43%",                     # derive() 先算好的
    "餐飲佔支出 69.8%",                   # 6000 / 8600
    "這個月還剩 1,400",
    "存下 1.1 萬",                        # 11400 寫成萬
    "10 月記了 2 筆",
])
def test_有出處的數字(text):
    assert advice.grounded({"title": "", "body": text, "basis": []}, advice.allowed_numbers(NUMBERS))


@pytest.mark.parametrize("text", ["支出 8,700", "已經用掉 87%", "一年可以省 51,600", "存下 1.3 萬"])
def test_模型自己算出來或編的數字(text):
    assert not advice.grounded({"title": "", "body": "", "basis": [text]}, advice.allowed_numbers(NUMBERS))


@pytest.mark.parametrize("text, wrong", [
    ("交通花了 6,000，要注意", True),                  # 6,000 是餐飲的
    ("交通佔支出 69.8%", True),                        # 69.8% 是餐飲的比例
    ("餐飲 6,000，交通 2,600", False),
    ("餐飲 6,000 佔支出 69.8%", False),
    ("交通 2,600，總支出 8,600", False),               # 8,600 是總數，不屬於任何分類
    ("這個月支出 8,600", False),
])
def test_數字有出處但套錯分類(text, wrong):
    assert advice.mislabeled({"title": "", "body": text, "basis": []}, NUMBERS) is wrong


def test_數字對不上或套錯分類的那一則_不顯示_其他照舊(monkeypatch):
    calls = []
    good = {"level": "warn", "title": "快用完了", "body": "已經用掉 86%。", "basis": ["支出 8,600 ÷ 可以花 10,000"],
            "suggest": ["每週少外食 2 次"], "conf": 0.9}
    made_up = {**good, "body": "照這樣一年會花 103,200。"}
    swapped = {**good, "title": "交通太多", "body": "交通花了 6,000。"}
    monkeypatch.setattr(client, "is_configured", lambda: True)
    monkeypatch.setattr(client, "complete_json",
                        lambda prompt, **kw: calls.append((prompt, kw)) or {"advices": [good, made_up, swapped]})
    out = advice.write_advices(NUMBERS, "")
    assert [a["title"] for a in out] == ["快用完了"] and out[0]["conf"] == 0.9
    prompt, kw = calls[0]
    assert kw["purpose"] == "advice" and kw["schema"] is advice.ADVICE_SCHEMA
    assert "換算好的比例" in prompt and "43.0" in prompt
    # 線上實測寫出「已存下 30140 元」「遠低於可支配上限的 68.3%」：數字對、說法錯，數字檢查抓不到，靠規則先講清楚
    assert "不要寫「已存下」" in kw["system"] and "遠低於" in kw["system"]
    # 全部不合格：不要硬回一堆錯的數字，丟 ModelError（路由回 503，前端用同一批數字自己寫）
    monkeypatch.setattr(client, "complete_json", lambda prompt, **kw: {"advices": [made_up, swapped]})
    with pytest.raises(client.ModelError):
        advice.write_advices(NUMBERS, "")


def test_微調的訓練資料_prompt_跟上線一字不差():
    """改了 parse.build_prompt 卻沒重跑 ml/build_sft.py，微調出來的模型上線時看到的就是沒看過的 prompt。"""
    import io

    ml = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "ml", "data")
    with io.open(os.path.join(ml, "train.jsonl"), encoding="utf-8") as f:
        train = {r["id"]: r for r in map(json.loads, filter(str.strip, f))}
    with io.open(os.path.join(ml, "sft.jsonl"), encoding="utf-8") as f:
        sft = [json.loads(next(f)) for _ in range(5)]
    with io.open(os.path.join(ml, "tools.json"), encoding="utf-8") as f:
        tools = json.load(f)
    assert tools[0]["function"]["parameters"] == parse.RECORD_TOOL["input_schema"], "重跑 python ml/build_sft.py"
    for row in sft:
        ex = train[row["id"]]
        system, prompt = parse.build_prompt(ex["text"], ex["categories"], ex["today"])
        assert row["messages"][0]["content"] == system, "重跑 python ml/build_sft.py"
        assert row["messages"][1]["content"] == prompt, "重跑 python ml/build_sft.py"


def test_推理型模型先想再答_只讀答案(monkeypatch):
    """DeepSeek-R1 這類模型會先輸出 <think>…</think>，裡面可能也有大括號，不能當成答案。"""
    content = '<think>使用者說 {早餐} 55 元……應該是餐飲</think>\n{"items": []}'
    http, _ = _openai(monkeypatch, (200, {"choices": [{"message": {"content": content}}]}))
    assert client.complete_json("x", client=http) == {"items": []}
    assert client._strip_thinking("<think>a</think>答案") == "答案"
    assert client._strip_thinking("沒有思考") == "沒有思考"


def test_想到一半被截斷_丟_ModelError(monkeypatch):
    http, _ = _openai(monkeypatch, (200, {"choices": [{"message": {"content": "<think>還在想……"}}]}))
    with pytest.raises(client.ModelError):
        client.complete_json("x", client=http)


def test_MODEL_MAX_TOKENS_只會放寬不會縮小(monkeypatch):
    http, sent = _openai(monkeypatch, *[(200, {"choices": [{"message": {"content": "{}"}}]})] * 2)
    monkeypatch.setattr(settings, "model_max_tokens", 4096)
    client.complete_json("x", max_tokens=1024, client=http)
    monkeypatch.setattr(settings, "model_max_tokens", 100)
    client.complete_json("x", max_tokens=1024, client=http)
    assert [b["max_tokens"] for b in sent] == [4096, 1024]


# ===========================================================================
# 備註只留「買了什麼」（使用者 2026-10-20）
# ===========================================================================
ITEM_CASES = [
    ("接著去學校買了10元自動鉛筆", "", "自動鉛筆"),
    ("我晚上去7-11買了10元奶茶", "7-11", "奶茶"),
    ("中午跟同事吃飯320", "", "吃飯"),
    ("昨天全聯買衛生紙199", "全聯", "衛生紙"),
    ("加油1200", "", "加油"),
    ("買了一杯珍奶60", "", "珍奶"),
    ("小孩補習費四千五", "", "補習費"),
    ("去看電影花了560", "", "看電影"),
    ("繳電費2400", "", "電費"),
    ("跟朋友喝咖啡150", "路易莎", "咖啡"),
]


def test_備註只留買了什麼_模型給的乾淨備註照用():
    for span, merchant, want in ITEM_CASES:
        assert parse.item_of("", span, merchant) == want, span
        assert parse.item_of(span, span, merchant) == want, "整段原句當備註也要整理：" + span
    assert parse.item_of("奶茶", "我晚上去7-11買了10元奶茶", "7-11") == "奶茶"
    assert parse.item_of("早餐", "早餐55") == "早餐"


def test_解析結果的備註不會是整段原句():
    cats = [{"id": "1", "name": "餐飲", "kind": "expense"}, {"id": "6", "name": "教育", "kind": "expense"}]
    text = "我晚上去7-11買了10元奶茶 接著去學校買了10元自動鉛筆"
    data = {"items": [
        {"span": "我晚上去7-11買了10元奶茶", "date": "2026-10-20", "amount": 10, "kind": "expense", "cat": "1",
         "merchant": "7-11", "note": "我晚上去7-11買了10元奶茶", "conf": {"date": 1, "amount": 1, "kind": 1, "cat": 1}},
        {"span": "接著去學校買了10元自動鉛筆", "date": "2026-10-20", "amount": 10, "kind": "expense", "cat": "6",
         "merchant": "", "note": "接著去學校買了10元自動鉛筆", "conf": {"date": 1, "amount": 1, "kind": 1, "cat": 1}},
    ]}
    items = parse.postprocess(data, cats, "2026-10-20", text)
    assert [i["note"] for i in items] == ["奶茶", "自動鉛筆"]


def test_前端規則備援整理備註_跟後端同一套():
    """模型叫不動時前端用規則頂著（api.js 的 itemOf）：結果要跟後端 item_of 一樣。"""
    import shutil
    import subprocess

    if not shutil.which("node"):
        pytest.skip("這台機器沒有 node")
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    src = open(os.path.join(repo, "frontend", "js", "api.js"), encoding="utf-8").read()
    snippet = src[src.index("  var IT = {"):src.index("  function parseLine(text)")]
    script = snippet + "\nconst cases = %s;\nprocess.stdout.write(JSON.stringify(cases.map(c => itemOf(c[0], c[1]))));" % \
        json.dumps([[s, m] for s, m, _w in ITEM_CASES], ensure_ascii=False)
    out = subprocess.run(["node", "-e", script], capture_output=True, check=True)
    got = json.loads(out.stdout.decode("utf-8"))
    assert got == [w for _s, _m, w in ITEM_CASES]
