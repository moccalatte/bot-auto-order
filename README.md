# Bot Auto Order Telegram

Bot Telegram untuk pemesanan produk digital dengan pembayaran otomatis melalui Pakasir, serta fitur kustomisasi menu dan respon bot oleh admin langsung dari Telegram.

## Struktur Proyek
- `src/`
  - `core/` – konfigurasi, logging, utilitas umum, **custom_config.py** (manajemen konfigurasi kustom admin: backup, restore, validasi, audit).
  - `bot/` – handler Telegram, template pesan, keyboard, anti-spam, **admin/** (modul menu admin & kustomisasi).
  - `services/` – integrasi Pakasir, Postgres, keranjang & pembayaran.
  - `webhooks/` – endpoint Pakasir (`/webhooks/pakasir`).
  - `main.py` – titik masuk bot Telegram.
  - `server.py` – server aiohttp untuk webhook Pakasir.
- `logs/` – keluaran log runtime (`logs/<service>/<tanggal>.log`).
- `tests/` – tempat uji unit/integrasi.
- `requirements.txt` – dependency Python.
- `.env.example` – template environment.
- `.gitignore` – aturan berkas yang diabaikan Git.

## Fitur Utama
- **Menu Admin Telegram**: Admin dapat mengakses menu khusus untuk:
  - Kelola respon/template pesan bot (order masuk, pembayaran, dsb) langsung dari Telegram.
  - CRUD produk dan upload gambar.
  - Kelola order (lihat, update status).
  - Kelola user (lihat, blokir/unblokir).
- **Kustomisasi Respon Bot**: Template pesan dapat diubah admin, dengan preview dan validasi placeholder (`{nama}`, `{order_id}`, dll).
- **Backup & Restore Konfigurasi**: Semua perubahan disimpan di database, dapat dibackup dan direstore oleh admin.
- **Audit Log**: Setiap perubahan konfigurasi tercatat untuk audit owner.
- **Validasi Input**: Semua input admin divalidasi sebelum disimpan.
- **Rollback**: Bot dapat rollback ke default jika terjadi error konfigurasi.
- **Privasi & Keamanan**: Data pribadi buyer/seller dijaga, hanya admin berwenang yang bisa akses. Owner dapat override dan audit penuh.
- **Notifikasi Owner**: Semua transaksi dan perubahan penting ada notifikasi ke owner.
- **Anti-Spam & Rate Limit**: Fitur keamanan aktif sesuai project_rules.md.

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

## Observability & Audit
- Semua log runtime dan audit perubahan konfigurasi tersimpan di `logs/<service>/<YYYY-MM-DD>.log` dengan format `[timestamp] [level] message`.
- Metrik ringan (jumlah transaksi, error, perubahan konfigurasi) dicatat oleh `TelemetryTracker` dan modul audit.
- Audit owner dapat dilakukan hanya lewat isi folder `/logs/`.

## Keamanan & Anti-Spam
- Guard anti-spam bawaan memblokir aksi yang lebih cepat dari ambang 1 detik secara beruntun.
- Ketika spam terdeteksi, bot otomatis mengirim peringatan ke user (`🚫 Jangan spam ya, tindakanmu akan dilaporkan ke admin.`).
- Semua admin pada `TELEGRAM_ADMIN_IDS` menerima laporan percobaan spam.
- Data pribadi buyer/seller dijaga privasinya, hanya admin berwenang yang bisa mengakses.

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

## Cara Kustomisasi Bot oleh Admin
1. Admin kirim `/admin` di Telegram untuk membuka menu admin.
2. Pilih submenu: Kelola Respon Bot, Produk, Order, atau User.
3. Untuk kustomisasi respon, pilih template yang ingin diubah, edit, dan preview sebelum publish.
4. Semua perubahan divalidasi (placeholder, format) dan disimpan di database.
5. Admin dapat backup/restore konfigurasi dari menu admin.
6. Owner dapat audit semua perubahan melalui log.

## Rollback & Recovery
- Jika terjadi error konfigurasi, bot otomatis rollback ke default.
- Backup konfigurasi dapat direstore oleh admin.
- Semua perubahan tercatat di audit log.

## Lisensi
Internal use only.
