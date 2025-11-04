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
  - Melihat (preview) template pesan bot yang aktif.
  - CRUD produk (tanpa unggah gambar).
  - Kelola order (lihat, update status).
  - Kelola user (lihat, blokir/unblokir).
  - Kelola voucher (generate, lihat, nonaktifkan) beserta rentang masa berlaku dengan pencatatan log penuh.
- **Kustomisasi Respon Bot**: Template pesan hanya bisa **dipreview** melalui menu admin; perubahan dilakukan oleh owner melalui pipeline terkontrol dengan validasi placeholder (`{nama}`, `{order_id}`, dll).
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
- **Wajib (produksi, semua layanan sekaligus):**
  ```bash
  export TELEGRAM_WEBHOOK_URL=https://example.com/telegram
  export PAKASIR_HOST=0.0.0.0        # opsional
  export PAKASIR_PORT=9000           # opsional
  bash scripts/run_stack.sh
  ```
  Perintah di atas menjalankan bot Telegram dalam mode webhook **dan** server webhook Pakasir dalam satu proses shell (cocok untuk 1 VPS yang menampung beberapa bot).

- **Alternatif (mode polling, hanya bot):**
  ```bash
  python -m src.main
  ```
- **Alternatif (jalankan manual terpisah):**
  ```bash
  python -m src.main --webhook --webhook-url https://example.com/telegram
  python -m src.server --host 0.0.0.0 --port 9000
  ```

## Observability & Audit
- Semua log runtime dan audit perubahan konfigurasi tersimpan di `logs/<service>/<YYYY-MM-DD>.log` dengan format `[timestamp] [level] message`.
- Metrik ringan (jumlah transaksi, error, perubahan konfigurasi) dicatat oleh `TelemetryTracker` dan modul audit.
- Audit owner dapat dilakukan hanya lewat isi folder `/logs/`.
- Setiap aksi admin penting (produk, order, voucher, blokir user) juga ditulis dalam format JSON ke `logs/audit/<YYYY-MM-DD>.log` untuk bukti sengketa.

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
2. Pilih submenu: Kelola Respon Bot (preview saja), Produk, Order, User, atau Voucher.
3. Ikuti instruksi yang muncul (format input ditampilkan pada setiap aksi).
4. Perubahan template dilakukan oleh owner; admin hanya dapat melakukan preview untuk memastikan pesan yang sedang aktif.
5. Saat memperbarui status order, gunakan format `order_id|status|catatan(optional)`; catatan hanya diperlukan bila pembayaran manual/deposit dan berisi bukti singkat (misal nomor referensi transfer). Semua perubahan data (produk/order/user/voucher) divalidasi sebelum disimpan dan otomatis tercatat di log untuk owner (termasuk pengaturan masa berlaku & batas voucher).
6. Owner dapat audit semua perubahan melalui log.

## Rollback & Recovery
- Jika terjadi error konfigurasi, bot otomatis rollback ke default.
- Backup konfigurasi dapat direstore oleh admin.
- Semua perubahan tercatat di audit log.

## Lisensi
Internal use only.
