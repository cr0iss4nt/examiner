FROM python:3.14-slim

WORKDIR /app

# Чтобы pip не писал в stdout
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PYTHONUNBUFFERED=1

# Ставим зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем приложение
COPY app ./app
COPY main.py .

# Открываем порт, который использует uvicorn
EXPOSE 8000

# Запуск FastAPI
#CMD ["uvicorn", "main", "--host", "0.0.0.0", "--port", "8000"]
CMD ["python", "../main.py"]

