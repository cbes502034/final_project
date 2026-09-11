"""Pydantic 模型：定義 API 進出的資料長什麼樣。

models/ 是「資料庫裡存什麼」，schemas/ 是「API 收送什麼」，
兩者刻意分開。例如 User 資料表有 password_hash，
但任何一個回應 schema 都不該有這一欄。

TODO(全員): 各自補上自己模組的 Request / Response 模型。
"""
