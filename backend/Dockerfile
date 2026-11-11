# Домашний склад — REST API (FastAPI + uvicorn).
# Сборка: docker build -t home-storage-api ./backend
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

# DATA_FILE по умолчанию /data/inventory.xlsx — том подкладывается в /data.
CMD ["python", "-m", "uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
