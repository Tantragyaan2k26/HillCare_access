FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY packages/ packages/
RUN pip install -e packages/geoengine && pip install -e packages/pipeline

COPY apps/api/ apps/api/
COPY data/ data/

ENV PYTHONPATH="/app/packages/geoengine/src:/app/packages/pipeline/src:/app/apps/api/src"

EXPOSE 8000

CMD ["uvicorn", "apps.api.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
