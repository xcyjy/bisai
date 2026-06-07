# 后端镜像（本地 compose 与云端 compose 共用）
FROM python:3.12-slim

WORKDIR /app

# 系统依赖（psycopg / bcrypt 编译所需的最小集合）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
