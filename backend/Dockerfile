FROM python:3.12-slim

WORKDIR /app

# 先裝相依，讓這一層可以被快取
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
# 先把資料表升到最新版再啟動（alembic/versions/）
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
