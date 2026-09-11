"""
模型呼叫。刻意拆成三個檔案，因為有三個人要動這一塊。

    client.py   成員1   共用的傳輸層：逾時、重試、驗證。其他兩人呼叫它
    parse.py    成員2   段落記帳的 prompt
    advice.py   成員3   財務建議的 prompt

**不要把 prompt 寫進 client.py**，也不要在 parse.py 裡自己寫 httpx 呼叫。
拆開的唯一目的就是讓三個人不會改到同一個檔案。
"""
