FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --prefix=/install -r requirements.txt

# Salin kode untuk kebutuhan instalasi tambahan (qrcode dsb)
COPY . .

# Pastikan skrip bisa dieksekusi di tahap akhir
RUN chmod +x scripts/run_stack.sh

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 libssl3 curl \
    && rm -rf /var/lib/apt/lists/*

# Salin dependency yang sudah diinstall dari tahap builder
COPY --from=builder /install /usr/local

# Salin kode aplikasi
COPY . .

RUN chmod +x scripts/run_stack.sh

ENTRYPOINT ["./scripts/run_stack.sh"]
