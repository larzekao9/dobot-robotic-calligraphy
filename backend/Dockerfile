FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml alembic.ini ./
COPY alembic ./alembic
COPY app ./app
RUN pip install --no-cache-dir -e .
CMD ["sh", "-c", "alembic upgrade head && python -m app.seeds && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
