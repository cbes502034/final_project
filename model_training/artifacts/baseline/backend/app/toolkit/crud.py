"""
資料庫的增刪改查。**不用自己寫 SQL**，任何一張表（app/models/ 的類別）都用同一組函式。

負責人：成員1（共用元件）——四個人都直接呼叫，不要各自再包一層

===========================================================================
五支就夠：參數決定做什麼
===========================================================================
    get(Model, id | where=..., fields=...)       拿一筆；或只拿一個欄位的值
    find(Model, where, ...)                      拿很多筆；篩選、排序、分頁、只取欄位、只數筆數
    save(Model, data, where=..., upsert=...)     新增一筆／很多筆、修改、找不到就新增
    remove(Model, where | id=..., soft=...)      刪除、刪很多筆、軟刪除（只設時間欄位）
    to_dict(row, ...)                            轉成回給前端的 dict（id 轉字串、時間轉字串、藏機密欄位）
另外兩支簡寫：count(...)、exists(...)。

跟 MineMarket 的 models.py 是同一個想法——getUser({"token": t}, "token")：
一支函式、條件用 dict、要哪些欄位用參數說。差別是這裡不綁某一張表，也不用手拼 SQL（不會有注入）。

===========================================================================
where 怎麼寫
===========================================================================
    {"user_id": 3}                        等於（值是 None → IS NULL）
    {"amount__gte": 100}                  gt／gte／lt／lte／ne
    {"id__in": [1, 2, 3]}                 在清單裡（notin：不在）
    {"note__contains": "早餐"}             包含；icontains 不分大小寫
    {"merchant__startswith": "全"}         開頭是（endswith：結尾是）
    {"removed_at__isnull": True}          是 NULL（False = 不是 NULL）
    {"occurred_on__between": (a, b)}      兩端都包含
    {"or": [{"user_id": 3}, {"group_id": 5}]}   任一成立（and 同理）
    [Transaction.amount > 100]            也可以直接放 SQLAlchemy 的條件（清單）
欄位名字打錯會直接丟 ValueError 並講出是哪張表、哪個欄位，不會默默查不到。

===========================================================================
交易（一起成功或一起失敗）
===========================================================================
每一支都收 db=...：
    * 不傳：自己開一個 session，做完 commit、出錯 rollback、最後關掉
    * 傳了（例如路由的 Depends(get_db)，或 with session_scope() as db）：
      用你的、**不 commit**，交給外面決定——好幾步要一起成功時就這樣用

        with session_scope() as db:
            fam = save(Family, {"name": "王家", "created_by": me.id}, db=db)
            save(FamilyMember, {"family_id": fam.id, "user_id": me.id, "role": "parent"}, db=db)

===========================================================================
例子
===========================================================================
    get(User, 3)                                          → User 物件或 None
    get(User, where={"email": "a@x.tw"}, fields="id")     → 3
    get(User, 3, fields=("email", "display_name"))        → {"email": ..., "display_name": ...}
    get(Group, 9, missing=errors.not_found("找不到這本帳"))   → 找不到直接丟那個例外

    find(Transaction, {"user_id__in": users, "occurred_on__between": (a, b)}, order_by="-occurred_on")
    find(Transaction, {"group_id": 5}, page=2, size=50)   → {"items", "total", "page", "size", "pages"}
    find(Transaction, {"user_id": 3}, count=True)         → 42
    find(Category, {"family_id__isnull": True}, fields="name")   → ["餐飲", "交通", ...]

    save(Group, {"name": "家用", "created_by": 1})          → 新的 Group
    save(Transaction, [{...}, {...}])                     → [Transaction, Transaction]（同一個交易）
    save(Transaction, {"id": 7, "amount": 180})           → 改第 7 筆（找不到丟 NotFound）
    save(Group, {"archived_at": now}, where={"id": 9})    → 改了幾筆
    save(AlertRule, {"enabled": True}, where={"user_id": 1, "percent": 80}, upsert=True)  → 有就改、沒有就新增

    remove(Transaction, id=7)                             → 1
    remove(Transaction, {"id__in": ids, "user_id": me.id})  → 刪了幾筆
    remove(Group, id=9, soft="archived_at")               → 不真的刪，設 archived_at = 現在
    remove(Guardianship, {"ward_id": 4}, soft={"ended_at": now})
"""

from __future__ import annotations

import math
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Mapping, Sequence

from sqlalchemy import and_, delete, func, inspect, or_, select, update
from sqlalchemy.orm import Session

from app.toolkit.db import session_scope

__all__ = ["NotFound", "get", "find", "save", "remove", "count", "exists", "to_dict", "build_where", "SENSITIVE"]

#: 永遠不回給前端的欄位。to_dict 預設會拿掉——忘了一次就是把密碼雜湊送出去
SENSITIVE = ("password_hash", "refresh_token_hash", "token_hash", "code_hash", "avatar_bytes", "ip_hash")

_OPS = ("gte", "gt", "lte", "lt", "ne", "in", "notin", "contains", "icontains",
        "startswith", "endswith", "isnull", "between")


class NotFound(LookupError):
    """get(..., missing="raise") 或 save 帶主鍵卻找不到時丟出。路由層轉成 404。"""


# ---------------------------------------------------------------------------
# 條件
# ---------------------------------------------------------------------------
def _column(model: Any, name: str):
    col = getattr(model, name, None)
    if col is None or not hasattr(col, "property"):
        cols = [c.key for c in inspect(model).mapper.column_attrs]
        raise ValueError("%s 沒有欄位「%s」。有的欄位：%s" % (model.__name__, name, "、".join(cols)))
    return col


def _clause(model: Any, key: str, value: Any):
    name, _, op = key.partition("__")
    if op and op not in _OPS:
        raise ValueError("看不懂的條件「%s」。可以用：%s" % (key, "、".join(_OPS)))
    col = _column(model, name)
    if not op:
        return col.is_(None) if value is None else col == value
    if op == "gt":
        return col > value
    if op == "gte":
        return col >= value
    if op == "lt":
        return col < value
    if op == "lte":
        return col <= value
    if op == "ne":
        return col.is_not(None) if value is None else col != value
    if op == "in":
        return col.in_(list(value))
    if op == "notin":
        return col.not_in(list(value))
    if op == "contains":
        return col.contains(value, autoescape=True)
    if op == "icontains":
        return func.lower(col).contains(str(value).lower(), autoescape=True)
    if op == "startswith":
        return col.startswith(value, autoescape=True)
    if op == "endswith":
        return col.endswith(value, autoescape=True)
    if op == "isnull":
        return col.is_(None) if value else col.is_not(None)
    lo, hi = value                                        # between
    return col.between(lo, hi)


def build_where(model: Any, where: Mapping[str, Any] | Sequence[Any] | None):
    """把 where（dict 或 SQLAlchemy 條件清單）變成一個條件；沒有條件回 None。"""
    if where is None:
        return None
    if isinstance(where, Mapping):
        parts = []
        for key, value in where.items():
            if key in ("or", "and"):
                subs = [build_where(model, w) for w in value]
                subs = [x for x in subs if x is not None]
                if subs:
                    parts.append(or_(*subs) if key == "or" else and_(*subs))
            else:
                parts.append(_clause(model, key, value))
        return and_(*parts) if parts else None
    parts = list(where)
    return and_(*parts) if parts else None


def _order(model: Any, order_by: Any) -> list:
    if order_by is None:
        return []
    items = [order_by] if isinstance(order_by, (str,)) or not isinstance(order_by, Iterable) else list(order_by)
    out = []
    for o in items:
        if isinstance(o, str):
            desc = o.startswith("-")
            col = _column(model, o.lstrip("-+"))
            out.append(col.desc() if desc else col.asc())
        else:
            out.append(o)
    return out


def _pk_names(model: Any) -> list[str]:
    return [c.key for c in inspect(model).mapper.primary_key]


def _surrogate_pk(model: Any) -> bool:
    """主鍵是不是「資料庫自己編號的整數 id」。是的話，帶 id 就是要改既有的那一筆。"""
    cols = inspect(model).mapper.primary_key
    if len(cols) != 1:
        return False
    try:
        return cols[0].type.python_type is int
    except Exception:          # 有些型別（例如 JSON）說不出自己的 Python 型別
        return False


# ---------------------------------------------------------------------------
# 查
# ---------------------------------------------------------------------------
def _shape(row: Any, fields: Any):
    if row is None or fields is None:
        return row
    if isinstance(fields, str):
        return getattr(row, fields)
    return {f: getattr(row, f) for f in fields}


def get(
    model: Any,
    id: Any = None,
    *,
    where: Mapping[str, Any] | Sequence[Any] | None = None,
    fields: str | Sequence[str] | None = None,
    order_by: Any = None,
    for_update: bool = False,
    missing: Any = None,
    db: Session | None = None,
):
    """拿一筆。

    參數
        id: 主鍵。複合主鍵傳 tuple，例如 get(FamilyMember, (family_id, user_id))
        where: 不用主鍵找時的條件（見檔頭）。符合多筆時拿 order_by 排第一的
        fields: 不給 → 物件；一個字串 → 那個欄位的值；清單 → dict
        for_update: 要改之前先鎖住這一列（PostgreSQL 的 SELECT ... FOR UPDATE），避免兩個請求同時改
        missing: 找不到時怎麼辦。None（預設）回 None；"raise" 丟 NotFound；
                 傳一個例外（例如 errors.not_found("找不到這本帳")）就丟那個
    """
    if id is None and where is None:
        raise ValueError("get 要給 id 或 where")
    with session_scope(db) as s:
        if id is not None and where is None and not for_update:
            row = s.get(model, id)
        else:
            stmt = select(model)
            if id is not None:
                pks = _pk_names(model)
                ids = id if isinstance(id, (tuple, list)) else (id,)
                stmt = stmt.where(and_(*[_column(model, k) == v for k, v in zip(pks, ids)]))
            cond = build_where(model, where)
            if cond is not None:
                stmt = stmt.where(cond)
            stmt = stmt.order_by(*_order(model, order_by)).limit(1)
            if for_update:
                stmt = stmt.with_for_update()
            row = s.execute(stmt).scalars().first()
        if row is None:
            if missing == "raise":
                raise NotFound("%s 找不到符合的資料" % model.__name__)
            if isinstance(missing, BaseException):
                raise missing
            return None
        return _shape(row, fields)


def find(
    model: Any,
    where: Mapping[str, Any] | Sequence[Any] | None = None,
    *,
    fields: str | Sequence[str] | None = None,
    order_by: Any = None,
    limit: int | None = None,
    offset: int | None = None,
    page: int | None = None,
    size: int | None = None,
    count: bool = False,
    distinct: bool = False,
    as_dict: bool = False,
    db: Session | None = None,
):
    """拿很多筆。

    回傳（依參數）
        預設                  list[物件]
        fields="name"          list[值]
        fields=("id","name")   list[dict]
        as_dict=True           list[dict]（經過 to_dict：id 轉字串、藏機密欄位）
        page=、size=           {"items": [...], "total": 全部幾筆, "page": 第幾頁, "size": 每頁幾筆, "pages": 共幾頁}
        count=True             int（只數，不拿資料）

    ⚠️ 分頁的 size 路由那層要設上限（toolkit/deps.py 的 paging 最多 200），這裡不替你擋。
    """
    cond = build_where(model, where)
    with session_scope(db) as s:
        if count:
            stmt = select(func.count()).select_from(model)
            if cond is not None:
                stmt = stmt.where(cond)
            return int(s.execute(stmt).scalar_one())

        if fields is not None and not as_dict:
            cols = [_column(model, fields)] if isinstance(fields, str) else [_column(model, f) for f in fields]
            stmt = select(*cols)
        else:
            stmt = select(model)
        if cond is not None:
            stmt = stmt.where(cond)
        if distinct:
            stmt = stmt.distinct()
        stmt = stmt.order_by(*_order(model, order_by))

        total = None
        if page is not None or size is not None:
            page = max(1, int(page or 1))
            size = max(1, int(size or 50))
            count_stmt = select(func.count()).select_from(model)
            if cond is not None:
                count_stmt = count_stmt.where(cond)
            total = int(s.execute(count_stmt).scalar_one())
            stmt = stmt.offset((page - 1) * size).limit(size)
        else:
            if offset:
                stmt = stmt.offset(offset)
            if limit:
                stmt = stmt.limit(limit)

        if fields is not None and not as_dict:
            result = s.execute(stmt)
            rows = [r[0] for r in result] if isinstance(fields, str) else [dict(r._mapping) for r in result]
        else:
            rows = list(s.execute(stmt).scalars())
            if as_dict:
                rows = [to_dict(r, fields=None if fields is None else ([fields] if isinstance(fields, str) else fields)) for r in rows]

        if total is None:
            return rows
        return {"items": rows, "total": total, "page": page, "size": size, "pages": max(1, math.ceil(total / size))}


def count(model: Any, where: Mapping[str, Any] | Sequence[Any] | None = None, *, db: Session | None = None) -> int:
    """find(..., count=True) 的簡寫。"""
    return find(model, where, count=True, db=db)


def exists(model: Any, where: Mapping[str, Any] | Sequence[Any] | None = None, *, db: Session | None = None) -> bool:
    """有沒有任何一筆符合。"""
    return get(model, where=where if where is not None else [], db=db) is not None


# ---------------------------------------------------------------------------
# 增、改
# ---------------------------------------------------------------------------
def _check_fields(model: Any, data: Mapping[str, Any]) -> None:
    for k in data:
        _column(model, k)


def save(
    model: Any,
    data: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    where: Mapping[str, Any] | Sequence[Any] | None = None,
    upsert: bool = False,
    allow_all: bool = False,
    db: Session | None = None,
):
    """新增或修改，看參數決定。

        data 是 dict、沒有 where、沒帶主鍵      → 新增一筆，回傳物件（已經有 id）
        data 是 list                           → 一次新增很多筆（同一個交易），回傳物件清單
        data 帶主鍵、沒有 where                 → 修改那一筆，回傳物件；找不到丟 NotFound（upsert=True 則新增）
                                                ⚠️ 複合主鍵的表（family_members、group_members）與自己給的 UUID：
                                                   找不到就是新增——那些表新增時本來就要帶主鍵
        有 where                               → 修改所有符合的，回傳改了幾筆
        有 where、upsert=True                  → 有符合的就改（回傳物件），沒有就用 where 的值 ＋ data 新增

    ⚠️ where 是空的會被擋：一行 bug 把整張表改掉的代價太大。真的要改全部請傳 allow_all=True。
    """
    with session_scope(db) as s:
        # 很多筆
        if isinstance(data, (list, tuple)):
            rows = []
            for item in data:
                _check_fields(model, item)
                row = model(**item)
                s.add(row)
                rows.append(row)
            s.flush()
            return rows

        _check_fields(model, data)
        pks = _pk_names(model)

        # 用 where 改
        if where is not None:
            cond = build_where(model, where)
            if cond is None and not allow_all:
                raise ValueError("save 的 where 是空的——會改到整張表。真的要這樣做請傳 allow_all=True")
            if upsert:
                stmt = select(model)
                if cond is not None:
                    stmt = stmt.where(cond)
                row = s.execute(stmt.limit(1)).scalars().first()
                if row is None:
                    seed = {k: v for k, v in dict(where).items() if "__" not in k and k not in ("or", "and")} \
                        if isinstance(where, Mapping) else {}
                    row = model(**{**seed, **dict(data)})
                    s.add(row)
                else:
                    for k, v in data.items():
                        setattr(row, k, v)
                s.flush()
                return row
            stmt = update(model).values(**dict(data))
            if cond is not None:
                stmt = stmt.where(cond)
            result = s.execute(stmt.execution_options(synchronize_session="fetch"))
            return int(result.rowcount or 0)

        # 帶主鍵：改那一筆
        if pks and all(data.get(k) is not None for k in pks):
            key = tuple(data[k] for k in pks)
            row = s.get(model, key if len(key) > 1 else key[0])
            if row is None:
                # 自動遞增的 id 找不到 → 一定是打錯了；複合主鍵（family_members…）或自己給的 UUID → 本來就是新增
                if not upsert and _surrogate_pk(model):
                    raise NotFound("%s 找不到主鍵 %s" % (model.__name__, key if len(key) > 1 else key[0]))
                row = model(**dict(data))
                s.add(row)
            else:
                for k, v in data.items():
                    if k not in pks:
                        setattr(row, k, v)
            s.flush()
            return row

        # 新增一筆
        row = model(**dict(data))
        s.add(row)
        s.flush()
        return row


# ---------------------------------------------------------------------------
# 刪
# ---------------------------------------------------------------------------
def remove(
    model: Any,
    where: Mapping[str, Any] | Sequence[Any] | None = None,
    *,
    id: Any = None,
    soft: str | Mapping[str, Any] | None = None,
    allow_all: bool = False,
    db: Session | None = None,
) -> int:
    """刪除，回傳影響了幾筆。

        remove(Model, id=7)                           刪一筆
        remove(Model, {"id__in": ids})                刪符合的
        remove(Model, id=9, soft="archived_at")       軟刪除：不刪，把那個時間欄位設成現在
        remove(Model, where, soft={"ended_at": now, "status": "removed"})   軟刪除改好幾個欄位

    ⚠️ 這個專案很多東西**不能真的刪**：封存帳本、解除監管、移出家庭、停權——全部是設時間欄位，
       因為稽核要看得到歷史、紀錄不能跟著不見。拿不準的時候用 soft。
    ⚠️ 沒有條件會被擋（allow_all=True 才能清整張表），跟 DELETE /api/transactions 沒帶 ids 一定要 400 是同一個道理。
    """
    conds = []
    if id is not None:
        pks = _pk_names(model)
        ids = id if isinstance(id, (tuple, list)) else (id,)
        conds.append(and_(*[_column(model, k) == v for k, v in zip(pks, ids)]))
    extra = build_where(model, where)
    if extra is not None:
        conds.append(extra)
    if not conds and not allow_all:
        raise ValueError("remove 沒有條件——會刪掉整張表。真的要這樣做請傳 allow_all=True")
    cond = and_(*conds) if conds else None

    with session_scope(db) as s:
        if soft is not None:
            values = {soft: datetime.now(timezone.utc)} if isinstance(soft, str) else dict(soft)
            _check_fields(model, values)
            stmt = update(model).values(**values)
        else:
            stmt = delete(model)
        if cond is not None:
            stmt = stmt.where(cond)
        result = s.execute(stmt.execution_options(synchronize_session="fetch"))
        return int(result.rowcount or 0)


# ---------------------------------------------------------------------------
# 轉成回給前端的樣子
# ---------------------------------------------------------------------------
def _jsonable(key: str, value: Any, str_ids: bool) -> Any:
    if value is None:
        return None
    if str_ids and (key == "id" or key.endswith("_id") or key == "created_by") and isinstance(value, (int, uuid.UUID)):
        return str(value)                   # 契約：ID 一律是字串
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, bytes):
        return None
    return value


def to_dict(
    row: Any,
    fields: Sequence[str] | None = None,
    *,
    exclude: Sequence[str] = SENSITIVE,
    rename: Mapping[str, str] | None = None,
    extra: Mapping[str, Any] | None = None,
    str_ids: bool = True,
) -> dict:
    """ORM 物件 → 可以直接回給前端的 dict。

    參數
        fields: 只要這些欄位（不給就全部）
        exclude: 不要的欄位。預設拿掉 SENSITIVE（密碼雜湊、token 雜湊、大頭貼原始 bytes…）
        rename: 改名，例如 {"display_name": "name", "occurred_on": "date", "category_id": "cat"}——
                資料表的名字跟前端契約不一樣時用
        extra: 再加上幾個欄位（例如 JOIN 出來的 userName）
        str_ids: id、*_id 轉成字串（契約第 1 條：ID 是字串）

        to_dict(tx, rename={"occurred_on": "date", "category_id": "cat", "user_id": "user", "group_id": "group"})
    """
    if row is None:
        return {}
    if isinstance(row, Mapping):
        data = dict(row)
    else:
        data = {c.key: getattr(row, c.key) for c in inspect(row).mapper.column_attrs}
    keys = list(fields) if fields else list(data)
    out = {}
    for k in keys:
        if k in exclude:
            continue
        out[(rename or {}).get(k, k)] = _jsonable(k, data.get(k), str_ids)
    if extra:
        out.update(extra)
    return out
