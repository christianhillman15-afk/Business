FROM python:3.11-slim

WORKDIR /app

# Install core deps first for layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code.
COPY whalebot ./whalebot
COPY config.example.yaml ./config.example.yaml

# Use the mounted config.yaml if present, else fall back to the example so the
# container still starts and watches all of Polymarket with sane defaults.
CMD ["sh", "-c", "python -m whalebot run -c ${WHALEBOT_CONFIG:-config.yaml}"]
