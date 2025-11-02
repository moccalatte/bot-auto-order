# Bot Auto Order Telegram

Bot Telegram untuk pemesanan produk digital dengan pembayaran otomatis melalui Pakasir.

## Struktur Proyek
- `src/`
  - `core/` – konfigurasi, logging, utilitas umum.
  - `bot/` – handler Telegram, template pesan, keyboard, anti-spam.
  - `services/` – integrasi Pakasir, Postgres, keranjang & pembayaran.
  - `webhooks/` – endpoint Pakasir (`/webhooks/pakasir`).
  - `main.py` – titik masuk bot Telegram.
  - `server.py` – server aiohttp untuk webhook Pakasir.
- `logs/` – keluaran log runtime (`logs/<service>/<tanggal>.log`).
- `tests/` – tempat uji unit/integrasi.
- `requirements.txt` – dependency Python.
- `.env.example` – template environment.
- `.gitignore` – aturan berkas yang diabaikan Git.

## Prasyarat
- Python 3.12
- PostgreSQL 15+
- Virtual environment (`python -m venv venv`)

## Konfigurasi Lingkungan
Salin `.env.example` menjadi `.env`, lalu isi nilai berikut:
```
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_ADMIN_IDS=123456789,987654321
DATABASE_URL=postgresql://user:password@localhost:5432/bot_order
PAKASIR_PROJECT_SLUG=your-slug
PAKASIR_API_KEY=your-api-key
PAKASIR_PUBLIC_DOMAIN=https://pots.my.id
PAKASIR_WEBHOOK_SECRET=optional-secret
BOT_TIMEZONE=Asia/Jakarta
LOG_LEVEL=INFO
BOT_STORE_NAME=Bot Auto Order
```

## Setup & Jalankan
- **Wajib:** Aktifkan virtual environment & instal dependency:
  ```bash
  python -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ```
- **Wajib:** Siapkan database Postgres:
  ```bash
  createdb bot_order
  psql bot_order -f scripts/schema.sql
  ```
- **Wajib:** Jalankan bot (mode polling):
  ```bash
  python -m src.main
  ```
- **Opsional:** Jalankan webhook server:
  ```bash
  python -m src.main --webhook --webhook-url https://example.com/telegram
  ```
- **Opsional:** Jalankan server webhook Pakasir:
  ```bash
  python -m src.server --host 0.0.0.0 --port 9000
  ```

## Observability
- Seluruh log disimpan dengan format `[timestamp] [level] message` di `logs/telegram-bot/<YYYY-MM-DD>.log`.
- Metode `TelemetryTracker` menyimpan metrik ringan (total transaksi sukses, gagal, dll) dan menuliskannya secara berkala.

## Keamanan & Anti-Spam
- Guard anti-spam bawaan memblokir aksi yang lebih cepat dari ambang 1 detik secara beruntun.
- Ketika spam terdeteksi, bot otomatis mengirim peringatan ke user (`🚫 Jangan spam ya, tindakanmu akan dilaporkan ke admin.`).
- Semua admin pada `TELEGRAM_ADMIN_IDS` menerima laporan percobaan spam.

## Testing
- **Rekomendasi:** Tambahkan kredensial sandbox pada `.env`, lalu jalankan:
  ```bash
  pytest
  ```
  (Test suite minimal disediakan sebagai placeholder; lengkapi sesuai kebutuhan.)

## Produksi
- **Wajib:** Terapkan proses daemon (systemd, supervisord) untuk menjalankan bot.
- **Wajib:** Pastikan URL webhook Pakasir mengarah ke endpoint publik `/webhooks/pakasir`.
- **Rekomendasi:** Monitoring log dan metrik secara rutin untuk audit & pemeliharaan.

## Lisensi
Internal use only.
