FROM python:3.14-slim

WORKDIR /

# Чтобы pip не писал в stdout
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PYTHONUNBUFFERED=1

# Ставим зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем приложение
COPY app ./app
COPY main.py .
COPY .env .

# Открываем порт, который использует uvicorn
EXPOSE 8500

# Запуск FastAPI
#CMD ["uvicorn", "main", "--host", "0.0.0.0", "--port", "8500"]
CMD ["python", "main.py"]
#CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8500"]

