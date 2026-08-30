FROM python:3.12-slim

WORKDIR /srv
ENV PYTHONUNBUFFERED=1

COPY . .
# The dev extras (pytest, httpx) ship in the image so the suite can be run
# against the compose stack: docker compose exec api pytest
RUN pip install --no-cache-dir -e ".[dev]"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
