FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    DISPLAY=:99 \
    CHROME_BIN=/usr/bin/chromium \
    BRIDGE_DATA_DIR=/data \
    PORT=8080

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       chromium chromium-driver xvfb ca-certificates fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY persistent-browser/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY persistent-browser/server.py /app/server.py

RUN mkdir -p /data
VOLUME ["/data"]
EXPOSE 8080
CMD ["python", "/app/server.py"]
