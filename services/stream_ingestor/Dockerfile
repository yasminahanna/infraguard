FROM python:3.11-slim

WORKDIR /app

# opencv-python-headless still needs libglib at runtime
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

CMD ["python", "-u", "app/ingestor.py"]
