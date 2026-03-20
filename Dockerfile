FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml setup.py ./
COPY src/ src/

RUN pip install --no-cache-dir ".[faster-whisper]"

COPY . .

RUN mkdir -p /app/data

ENV DATA_DIR=/app/data
ENV WHISPER_MODEL=large-v3-turbo
ENV TRANSCRIBER_BACKEND=faster-whisper

EXPOSE 8000

CMD ["uvicorn", "transcribee.main:app", "--host", "0.0.0.0", "--port", "8000"]
