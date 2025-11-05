# Bot Auto Order Telegram

Bot Telegram untuk pemesanan produk digital dengan pembayaran otomatis melalui Pakasir, serta fitur kustomisasi menu dan respon bot oleh admin langsung dari Telegram.

> **Status:** ✅ Production Ready | **Version:** 0.2.1 | **Last Updated:** 2025-01-15

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
- `.env.example` – template environment (dev lokal).
- `bot.env.template` – template environment khusus tenant Docker Compose.
- `.gitignore` – aturan berkas yang diabaikan Git.

## Fitur Utama
- **Menu Admin Telegram**: Admin dapat mengakses menu khusus untuk:
  - Melihat (preview) template pesan bot yang aktif.
  - CRUD produk (tanpa unggah gambar).
  - Kelola order (lihat, update status).
  - Kelola user (lihat, blokir/unblokir).
  - Kelola voucher (generate, lihat, nonaktifkan) beserta rentang masa berlaku dengan pencatatan log penuh.
  - Kalkulator refund untuk perhitungan pengembalian dana (admin only via command).
- **Kustomisasi Respon Bot**: Template pesan hanya bisa **dipreview** melalui menu admin; perubahan dilakukan oleh owner melalui pipeline terkontrol dengan validasi placeholder (`{nama}`, `{order_id}`, dll).
- **Backup & Restore Konfigurasi**: Semua perubahan disimpan di database, dapat dibackup dan direstore oleh admin.
- **Audit Log**: Setiap perubahan konfigurasi tercatat untuk audit owner.
- **Validasi Input**: Semua input admin divalidasi sebelum disimpan.
- **Rollback**: Bot dapat rollback ke default jika terjadi error konfigurasi.
- **Privasi & Keamanan**: Data pribadi buyer/seller dijaga, hanya admin berwenang yang bisa akses. Owner dapat override dan audit penuh. Validasi input komprehensif untuk mencegah injection attacks.
- **Notifikasi Pesanan Baru ke Seller**: Order baru otomatis men-trigger pesan ringkas (tanpa owner) berisi data customer, produk, metode, dan timestamp lokal.
- **SNK Produk & Monitoring**: Admin dapat menambahkan Syarat & Ketentuan per produk; bot mengirim SNK setelah pembayaran, customer dapat mengirim bukti lewat tombol `Penuhi SNK`, dan admin menerima notifikasi + media.
- **Broadcast Pesan Custom**: Admin dapat mengirim teks atau foto ke semua user yang pernah `/start`, dengan penanganan otomatis untuk user yang memblokir bot.
- **Notifikasi Owner**: Semua transaksi dan perubahan penting ada notifikasi ke owner.
- **Anti-Spam & Rate Limit**: Fitur keamanan aktif sesuai project_rules.md.
- **UX Modern dengan HTML Formatting**: Semua pesan bot menggunakan HTML parse mode dengan bold untuk informasi penting dan emoji konsisten untuk pengalaman pengguna yang lebih baik.

## Prasyarat
- Python 3.12
- PostgreSQL 15+
- Virtual environment (`python -m venv venv`)

## Konfigurasi Lingkungan
Salin `.env.example` menjadi `.env`, lalu isi nilai berikut:
```
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_ADMIN_IDS=123456789,987654321
TELEGRAM_OWNER_IDS=111111111            # opsional, pisahkan dengan koma bila lebih dari satu
DATABASE_URL=postgresql://user:password@localhost:5432/bot_order
PAKASIR_PROJECT_SLUG=your-slug
PAKASIR_API_KEY=your-api-key
PAKASIR_PUBLIC_DOMAIN=https://pots.my.id
PAKASIR_WEBHOOK_SECRET=optional-secret
BOT_TIMEZONE=Asia/Jakarta
LOG_LEVEL=INFO
BOT_STORE_NAME=Bot Auto Order
DATA_ENCRYPTION_KEY=base64-fernet-key
OWNER_BOT_TOKEN=optional-owner-bot-token
SNK_RETENTION_DAYS=30
ENABLE_OWNER_ALERTS=true
OWNER_ALERT_THRESHOLD=ERROR
```
- `DATA_ENCRYPTION_KEY`: buat dengan `openssl rand -base64 32` (digunakan untuk mengenkripsi data SNK di database).
- `OWNER_BOT_TOKEN`: token bot khusus owner (jika tidak diisi, bot utama akan digunakan untuk notifikasi owner).
- `ENABLE_OWNER_ALERTS`: set `true` untuk mengaktifkan notifikasi otomatis ketika log level tinggi muncul.
- `ENABLE_AUTO_HEALTHCHECK` + `HEALTHCHECK_INTERVAL_MINUTES`: penjadwalan health-check internal (default 5 menit).
- `ENABLE_AUTO_BACKUP`, `BACKUP_TIME`, `BACKUP_AUTOMATIC_OFFSITE`: jadwal backup harian di container (default 00:00, offsite aktif).

## Setup & Jalankan
- **Persiapan lokal (opsional untuk pengembangan):**
  ```bash
  python -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  createdb bot_order
  psql bot_order -f scripts/schema.sql
  ```
- **Install dependencies lokal:**
  ```bash
  pip install -r requirements.txt
  ```
  **Catatan:** Requirements sudah include `python-telegram-bot[webhooks,job-queue]` untuk full functionality.
- **Build image produksi:**
  ```bash
  docker build -t bot-auto-order:0.2.1 .
  docker tag bot-auto-order:0.2.1 your-dockerhub-username/bot-auto-order:0.2.1
  docker push your-dockerhub-username/bot-auto-order:0.2.1
  ```
- **Provision tenant baru (otomatis):**
  ```bash
  python scripts/provision_tenant.py myshop qris \
    --image your-dockerhub-username/bot-auto-order:0.2.1 \
    --postgres-host db.internal --postgres-user bot_auto_order --postgres-password supersecret
  ```
  Skrip akan membuat folder `deployments/bot-myshop-qris/`, menyalin `compose.yml`, `bot.env`, serta README khusus dengan langkah lanjut. Edit `bot.env` untuk mengisi token/secret yang belum terisi (lihat komentar pada file).
- **Jalankan tenant:**
  ```bash
  cd deployments/bot-${STORE_SLUG}
  ./run.sh   # otomatis ekspor BOT_WEBHOOK_PORT, PAKASIR_PORT, IMAGE_NAME
  ```
-  Skrip `run.sh` membaca nilai dari `bot.env` (termasuk `BOT_WEBHOOK_PORT` & `PAKASIR_PORT`), lalu menjalankan `docker compose up -d`. Port default 8080 (Telegram webhook) dan 9000 (Pakasir webhook) bisa kamu ubah langsung di `bot.env`.
- **Skema database multi-tenant:** gunakan satu cluster PostgreSQL (mis. di VPS terpisah) dengan pola nama `db_<store_name>`. Isi `DATABASE_URL` pada `bot.env` sesuai database tenant.
- **Struktur hasil provisioning:**
  - `compose.yml` — definisi service Docker.
  - `bot.env` — environment khusus tenant (isi token & secret).
  - `logs/`, `backups/local`, `backups/offsite`, `logs/maintenance/` — destinasi log & backup.
  - `run.sh` — skrip untuk start/update container (`./run.sh`).
  - `README_TENANT.md` — ringkasan langkah lanjutan untuk tenant tersebut.
- **Catatan port:** `BOT_WEBHOOK_PORT` memetakan port host ke port internal 8080 (Telegram webhook). `PAKASIR_PORT` memetakan ke port internal 9000 (webhook Pakasir). Atur keduanya di `bot.env` jika butuh port unik.
- **(Opsional) Automasi health-check & backup dari host:**
  ```cron
  */5 * * * * DOCKER_COMPOSE_BIN="docker compose" \
    /opt/bot-auto-order/scripts/cron_healthcheck.sh /opt/bot-auto-order/deployments/bot-myshop-qris/compose.yml >> /opt/bot-auto-order/deployments/bot-myshop-qris/logs/maintenance/health.log 2>&1
  2 2 * * * BACKUP_ENCRYPTION_PASSWORD='rahasia-super' \
    /opt/bot-auto-order/scripts/cron_backup.sh /opt/bot-auto-order/deployments/bot-myshop-qris/compose.yml --offsite >> /opt/bot-auto-order/deployments/bot-myshop-qris/logs/maintenance/backup.log 2>&1
  ```
- **Catatan multi-tenant:** setiap folder `deployments/bot-<store>-<gateway>` menyimpan `compose.yml`, `bot.env`, `logs/`, `backups/`. Port berbeda dapat diatur via `BOT_WEBHOOK_PORT` dan `PAKASIR_PORT` agar tidak konflik antar tenant.

- **Mode CLI manual (tanpa Docker) untuk debugging cepat:**
  ```bash
  python -m src.main --mode polling
  python -m src.main --mode webhook --webhook-url https://example.com/telegram
  python -m src.server --host 0.0.0.0 --port 9000
  ```

## Observability & Audit
- Semua log runtime dan audit perubahan konfigurasi tersimpan di `logs/<service>/<YYYY-MM-DD>.log` dengan format `[timestamp] [level] message`.
- Metrik ringan (jumlah transaksi, error, perubahan konfigurasi) dicatat oleh `TelemetryTracker` dan modul audit.
- Audit owner dapat dilakukan hanya lewat isi folder `/logs/`.
- Setiap aksi admin penting (produk, order, voucher, blokir user) juga ditulis dalam format JSON ke `logs/audit/<YYYY-MM-DD>.log` untuk bukti sengketa.
- Jalankan `python -m src.tools.healthcheck` (via cron/systemd timer atau container scheduled task) untuk memeriksa Telegram API, koneksi database, dan kapasitas disk. Hasilnya ditulis ke `logs/health-check/<tanggal>.log` dan pemilik menerima alert jika ada kegagalan. Contoh log berada di `logs/health-check/sample.log`.
  - Threshold dapat diatur dengan env: `HEALTH_CPU_THRESHOLD`, `HEALTH_MEMORY_THRESHOLD`, `HEALTH_DISK_THRESHOLD`, `LOG_USAGE_THRESHOLD_MB`.
  - Secara default health-check berjalan otomatis di dalam container (interval `HEALTHCHECK_INTERVAL_MINUTES`, aktif jika `ENABLE_AUTO_HEALTHCHECK=true`). Gunakan skrip `scripts/cron_healthcheck.sh` hanya jika ingin penjadwalan di host.
- Backup terenkripsi: gunakan `python -m src.tools.backup_manager` untuk membuat, memverifikasi, restore, dan prune backup. Contoh:
  ```bash
  BACKUP_ENCRYPTION_PASSWORD='rahasia-super' python -m src.tools.backup_manager create --offsite
  python -m src.tools.backup_manager list
  python -m src.tools.backup_manager verify backups/local/backup-20250605-120000.tar.gz.enc
  BACKUP_ENCRYPTION_PASSWORD='rahasia-super' python -m src.tools.backup_manager restore backups/local/backup-20250605-120000.tar.gz.enc
  ```
  Variabel lingkungan:
  - `BACKUP_ENCRYPTION_PASSWORD` (wajib, AES-256 via OpenSSL)
  - `BACKUP_LOCAL_DIR` (default `backups/local`)
  - `BACKUP_OFFSITE_DIR` (default `backups/offsite`)
  - Backup otomatis di dalam container aktif jika `ENABLE_AUTO_BACKUP=true` (jadwal `BACKUP_TIME`, default 00:00). `BACKUP_AUTOMATIC_OFFSITE` menentukan apakah hasil juga disalin ke `BACKUP_OFFSITE_DIR`. Gunakan `scripts/cron_backup.sh` hanya bila ingin eksekusi dari host.

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
- **Manual Testing Checklist:**
  - ✅ Test `/start` command dengan format pesan dan keyboard yang benar
  - ✅ Verify inline keyboard kategori muncul di pesan pertama
  - ✅ Test customer tidak bisa akses Calculator dari reply keyboard (admin only via command)
  - ✅ Test semua pesan menggunakan HTML formatting dengan bold yang benar
  - ✅ Test payment flow lengkap dengan QRIS
  - ✅ Verify TELEGRAM_ADMIN_IDS dan TELEGRAM_OWNER_IDS parsing benar

## Produksi
- **Wajib:** Jalankan melalui Docker Compose (restart policy `always`) atau supervisor setara agar bot auto-restart.
- **Wajib:** Pastikan URL webhook Pakasir mengarah ke endpoint publik `/webhooks/pakasir`.
- **Rekomendasi:** Monitoring log dan metrik secara rutin untuk audit & pemeliharaan.

## Cara Kustomisasi Bot oleh Admin
1. Admin kirim `/admin` di Telegram untuk membuka menu admin.
2. Pilih submenu: Kelola Respon Bot (preview saja), Produk, Order, User, atau Voucher.
3. Ikuti instruksi yang muncul (format input ditampilkan pada setiap aksi).
4. Perubahan template dilakukan oleh owner; admin hanya dapat melakukan preview untuk memastikan pesan yang sedang aktif.
5. Saat memperbarui status order, gunakan format `order_id|status|catatan(optional)`; catatan hanya diperlukan bila pembayaran manual/deposit dan berisi bukti singkat (misal nomor referensi transfer). Semua perubahan data (produk/order/user/voucher) divalidasi sebelum disimpan dan otomatis tercatat di log untuk owner (termasuk pengaturan masa berlaku & batas voucher).
6. Owner dapat audit semua perubahan melalui log.
7. Setelah menambah produk, admin akan ditanya apakah ingin menambahkan SNK (Syarat & Ketentuan). Pilih **Tambah SNK** untuk langsung mengirim teks SNK atau **Skip SNK** bila belum diperlukan.
8. Gunakan submenu **📜 Kelola SNK Produk** (format `product_id|SNK baru` atau `product_id|hapus`) untuk memperbarui atau menghapus SNK produk kapan saja.
9. Gunakan menu **📣 Broadcast Pesan** untuk mengirim pengumuman ke seluruh user yang pernah `/start`. Kirim teks biasa atau foto dengan caption; ketik `BATAL` untuk membatalkan.
   - Setelah pesan dikirim, bot membuat job persisten (tabel `broadcast_jobs`) dan dispatcher akan menyalurkan pesan secara bertahap agar aman saat restart. Status job muncul di balasan bot dan detailnya ada di log.

## SNK & Monitoring
- Bot otomatis mengirim pesan SNK lengkap setelah order berstatus `paid/completed`, lengkap dengan tombol `✅ Penuhi SNK`.
- Customer yang menekan tombol dapat mengirim screenshot dan keterangan; bot menyimpan bukti di database (`product_term_submissions`) dan meneruskan ke seller/admin sebagai notifikasi (owner tidak menerima).
- Admin dapat meninjau bukti dari notifikasi Telegram dan log audit; data tersimpan untuk kepentingan SLA/garansi.
- Perubahan/hapus SNK akan mengirim notifikasi ke owner secara otomatis (audit realtime).

## Rollback & Recovery
- Jika terjadi error konfigurasi, bot otomatis rollback ke default.
- Backup konfigurasi dapat direstore oleh admin.
- Semua perubahan tercatat di audit log.
- Gunakan `python -m src.tools.backup_manager create --offsite` untuk membuat backup terenkripsi, dan `restore` untuk pemulihan. Jalankan `docker compose up -d` setelah restore.
- Catat setiap drill di `logs/maintenance/` untuk audit owner.

## Recent Fixes & Improvements (v0.2.1+)

### ✅ Configuration & Validation
- Fixed `TELEGRAM_ADMIN_IDS` and `TELEGRAM_OWNER_IDS` validator to handle single integer values
- Enhanced input validation across all admin functions

### ✅ Dependencies & Setup
- Updated `python-telegram-bot` to include `[job-queue]` support
- All scheduled tasks now work without warnings

### ✅ UX & UI Enhancements
- **Improved Welcome Message**: Inline keyboard kategori now appears in first message with better formatting
- **HTML Parse Mode**: All bot messages now use HTML formatting with `<b>bold</b>` for important info
- **Consistent Emoji Usage**: Modern, consistent emoji design across all messages
- **Calculator Access Control**: Calculator menu removed from customer view (admin only via `/refund_calculator` and `/set_calculator`)
- **Better Visual Hierarchy**: Bold for headers, italic for disclaimers, `<code>` for IDs

### ✅ Code Quality
- All message templates migrated from Markdown to HTML
- Added `parse_mode=ParseMode.HTML` consistently across 10+ handler functions
- No bare exceptions or SQL injection vulnerabilities detected
- Comprehensive error handling throughout codebase

### 📝 Documentation Updates
- Updated `docs/fixing_plan.md` with complete fix status
- All critical issues resolved and tested
- Testing checklist added for deployment verification

For detailed fix history, see `docs/fixing_plan.md`.

## Pre-Production Checklist
- **Chaos test**: `docker compose kill` lalu pastikan container restart dan job SNK/broadcast tetap berjalan (cek log `[broadcast_queue]`).
- **Backup drill**: `backup_manager create → verify → restore` di staging, catat hasilnya.
- **Gateway simulation**: gunakan API `paymentsimulation` (lihat `docs/pakasir.md`) untuk memvalidasi alur sukses/gagal dan alert owner.
- **Resource exhaustion**: uji `healthcheck` dengan disk/RAM tertekan (misal `fallocate` + `stress`), pastikan alert owner diterima dan cleanup dilakukan.
- **Dependency check**: build image baru (`docker build -t bot-auto-order:staging .`) dan jalankan regresi sebelum produksi.

## Troubleshooting

### Port Already in Use
```bash
# Find process using port
sudo lsof -i :9000
# Kill process
kill <PID>
# Or kill by port
sudo fuser -k 9000/tcp
```

### Admin IDs Not Detected
Pastikan format di `.env` benar:
```
TELEGRAM_ADMIN_IDS=5473468582
TELEGRAM_OWNER_IDS=341404536
```
Untuk multiple IDs, pisahkan dengan koma tanpa spasi:
```
TELEGRAM_ADMIN_IDS=5473468582,123456789
```

### Bot Not Responding
1. Check logs: `tail -f logs/telegram-bot/$(date +%Y-%m-%d).log`
2. Verify token valid: `echo $TELEGRAM_BOT_TOKEN`
3. Test connection: `python -m src.main --mode polling`

## Lisensi
Internal use only.
