FROM python:3.13-slim

# Установка poetry
RUN pip install poetry

WORKDIR /app
COPY pyproject.toml poetry.lock* /app/

# Конфигурация poetry: не создавать виртуальное окружение внутри контейнера
RUN poetry config virtualenvs.create false && poetry install --no-root --no-interaction --no-ansi

COPY . /app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]