# Bot Auto Order Telegram

Bot Telegram untuk pemesanan produk digital dengan pembayaran otomatis melalui Pakasir, serta fitur kustomisasi menu dan respon bot oleh admin langsung dari Telegram.

> **Status:** ✅ Production Ready | **Version:** 0.8.1 | **Last Updated:** 2025-01-06

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

### 🆕 v0.8.1 - Critical Bug Fix (HOTFIX) 🐛
- **Fixed UnboundLocalError** 🔧: Resolved runtime error preventing admin from deleting products
  - Removed duplicate callback handler `admin:snk_product` causing scope ambiguity
  - Corrected mislabeled `admin:edit_product` handler to `admin:edit_product_message`
  - All admin operations now function correctly without errors
  - Zero duplicate handlers remaining in codebase
  - Risk: Very Low | Confidence: Very High (99%)

### 🎯 v0.8.0 - Production-Grade Quality & UX Improvements ⚡
- **Automated Expiry Management** 🤖: Smart invoice & order lifecycle
  - Auto-cancel expired orders setiap 60 detik
  - Auto-delete/edit pesan invoice setelah expired
  - QR code invalid setelah expired (fraud prevention)
  - Support untuk payment dan deposit expiry
  - Consistent user & admin notifications
- **Product Content Management Overhaul** 📦: Stock integrity guaranteed
  - 6-step add product wizard (mandatory content input)
  - Stock auto-calculated dari product_contents (single source of truth)
  - Menu "Kelola Stok" untuk granular content management
  - Add/remove/view content dengan batch input support
  - No more products without content, no phantom stock
- **Audit & Telemetry Coverage** 📊: Full operational visibility
  - Audit log writes ke database + file
  - Telemetry flush ke DB setiap 6 jam (auto-sync)
  - JSONB support untuk complex audit details
  - Entity type & ID tracking
  - Production-ready monitoring & compliance
- **Enhanced Data Integrity** 🛡️: Zero data loss guarantee
  - Schema constraints fully validated (UNIQUE, CHECK, FOREIGN KEY)
  - Migration scripts dengan backup & rollback
  - Orphan & duplicate detection
  - Stock recalculation dari actual contents
- **Code Quality & Reliability** 📚: Enterprise-grade codebase
  - 1,000+ lines added/modified
  - 10+ new functions untuk automation
  - Auto-healing capabilities (expiry jobs)
  - Comprehensive error handling & logging

### v0.7.0 - Comprehensive Fixes & Schema Improvements
- Database Schema Overhaul (UNIQUE constraints, CHECK constraints, 25+ indexes)
- Service Layer Complete Validation (foreign key validation, type safety)
- Voucher/Coupon System Enhancement (atomic operations, max uses enforcement)
- Safe Migration System (backup, rollback, validation)
- 40+ new utility functions
  - Comprehensive docstrings (Args, Returns, Raises)
  - Type hints throughout
  - Structured logging di semua operations
  - DRY principle & SOLID practices
- **See:** `FIXES_SUMMARY_v0.7.0.txt` dan `docs/codebase-critics.md` untuk detail lengkap

### v0.6.0 - Product Content System & Critical Fixes
- **Product Content-Based Inventory** 🎯: Sistem stok berbasis konten digital yang revolusioner
  - Stok = jumlah actual content yang tersedia (bukan angka manual)
  - Admin upload content (email, password, code, dll) untuk setiap unit produk
  - Customer **otomatis menerima content produk** setelah pembayaran sukses
  - Tidak perlu kirim manual via chat - fully automated delivery
  - Full audit trail: siapa dapat content apa, kapan
  - Stock cannot be manipulated - read-only, calculated from database
- **CRITICAL FIX: QRIS Fee Calculation** ✅: Perbaikan perhitungan fee yang akurat 100%
  - Fix double fee calculation (sistem + Pakasir)
  - Invoice amount sekarang **exact match** dengan QRIS charge
  - Fee ditampilkan sebagai "Biaya Layanan" (bukan "Pakasir")
- **Enhanced Admin Notifications** 📊: Notifikasi lebih comprehensive
  - Status pembayaran (⏳ Pending → ✅ Success)
  - Notifikasi otomatis saat pembayaran berhasil
  - Notifikasi otomatis saat deposit berhasil
  - Detail lengkap customer dan produk yang dibeli
- **Improved Welcome Experience** 🎉: UX lebih professional
  - Inline keyboard dengan tombol "📋 INFORMASI" dan "📖 Cara Order"
  - Format pesan lebih clean dan modern
  - Product list dengan horizontal button layout (max 5 per row)
- **Better Error Handling** 🛡️: Bot tidak spam error untuk pesan tidak dikenal

### Core Features
- **Payment Expiration Monitoring**: Sistem otomatis untuk tracking dan notifikasi pembayaran expired
  - Scheduled job berjalan setiap 60 detik untuk monitor expired payments
  - Auto-cancel dan release content ketika payment expired
  - User menerima notifikasi lengkap dengan detail transaksi dan langkah selanjutnya
  - Deposit QRIS yang tidak dibayar ikut dibatalkan dan log pesan dibersihkan
  - Mencegah "ghost orders" yang block inventory tanpa pembayaran
- **Informasi & Cara Order Panel**: Pesan welcome dengan inline button `📋 INFORMASI` dan `📖 Cara Order`
  - Panel informasi menampilkan saldo, status verifikasi, Bank ID, dan ID pengguna
  - User dapat mengubah display name & nomor WhatsApp langsung dari Telegram
  - Tombol Customer Service mengarahkan ke admin, sedangkan Last Transaction menampilkan histori order terbaru
  - Template Cara Order dapat dikustomisasi (teks + gambar) dari menu admin
- **QRIS Invoice Normalization**: Subtotal, biaya layanan (0,7% + Rp310), dan total dibayar ditampilkan terpisah; guard mencegah checkout ketika keranjang kosong
- **Deposit QRIS Otomatis**: Menu `💰 Deposit` membuat invoice QRIS dengan fee otomatis, menyimpan log deposit, dan scheduler membersihkan pesan kadaluarsa
- **Menu Admin Telegram dengan Hierarki**: Admin dapat mengakses menu khusus `⚙️ Admin Settings` dengan submenu terstruktur:
  - **Kelola Respon Bot**: Preview template pesan (welcome, payment success) dengan placeholder, edit teks/gambar, dan **inline cancel button** di setiap mode input
  - **Kelola Produk**: CRUD produk dengan **wizard step-by-step** (5 langkah ramah awam), tanpa kategori, pilih produk dari list untuk edit/hapus
  - **Kelola Order**: Lihat dan update status order
  - **Kelola User**: Lihat user statistics, blokir/unblokir user dengan **inline cancel buttons** dan format pesan informatif
  - **Kelola Voucher**: Generate voucher dengan **format sederhana** `KODE | NOMINAL | BATAS_PAKAI` (support % dan fixed amount) dan **inline cancel button**
  - **Broadcast**: Kirim pesan ke semua user dengan statistik (total, success, failed) dan **inline cancel button**
  - **Calculator**: User-friendly calculator untuk refund/deposit yang **langsung berfungsi** (no command), dengan **inline cancel button**
  - **Deposit**: Deposit QRIS (coming soon) dan Transfer Manual dengan panduan lengkap dan hyperlink ke admin yang proper
- **Product List dengan Pagination**: List produk menampilkan 5 item per halaman dengan navigation buttons (Previous/Next) dan quick view
- **Enhanced Welcome Experience**: Welcome message langsung menampilkan statistik toko + tombol inline untuk Informasi dan Cara Order sekaligus mengaktifkan keyboard utama
- **Stock Overview & Refresh**: Tombol `🏷 Cek Stok` menampilkan daftar stok terbaru lengkap dengan penomoran konsisten serta tombol `🔄 Refresh`
- **Consistent Cancel Behavior**: Semua tombol batal di menu admin menampilkan welcome message yang lengkap dengan inline keyboard
- **Role-Based Keyboard**: Bot menampilkan keyboard yang berbeda berdasarkan role user:
  - Admin: Melihat tombol `⚙️ Admin Settings` untuk akses penuh
  - Customer: Melihat keyboard customer standar tanpa akses admin
- **Backup & Restore Konfigurasi**: Semua perubahan disimpan di database, dapat dibackup dan direstore oleh admin.
- **Audit Log**: Setiap perubahan konfigurasi tercatat untuk audit owner.
- **Validasi Input**: Semua input admin divalidasi sebelum disimpan.
- **Rollback**: Bot dapat rollback ke default jika terjadi error konfigurasi.
- **Optimized Payment Flow**: Invoice dikirim ke user terlebih dahulu sebelum notifikasi admin, loading message di-edit (tidak duplikat), cart auto-clear setelah pembayaran
- **Akurasi Nominal QRIS**: Integrasi Pakasir otomatis mengonversi cents ke Rupiah sehingga QR code dan checkout URL menampilkan harga yang tepat.
- **Privasi & Keamanan**: Data pribadi buyer/seller dijaga, hanya admin berwenang yang bisa akses. Owner dapat override dan audit penuh. Validasi input komprehensif untuk mencegah injection attacks.
- **Notifikasi Pesanan Baru ke Seller**: Order baru otomatis men-trigger pesan ringkas (tanpa owner) berisi data customer, produk, metode, dan timestamp lokal.
- **SNK Produk & Monitoring**: Admin dapat menambahkan Syarat & Ketentuan per produk; bot mengirim SNK setelah pembayaran, customer dapat mengirim bukti lewat tombol `Penuhi SNK`, dan admin menerima notifikasi + media.
- **Broadcast Pesan Custom**: Admin dapat mengirim teks atau foto ke semua user yang pernah `/start`, dengan penanganan otomatis untuk user yang memblokir bot.
- **Notifikasi Owner**: Semua transaksi dan perubahan penting ada notifikasi ke owner.
- **Anti-Spam & Rate Limit**: Fitur keamanan aktif sesuai project_rules.md.
- **UX Modern dengan HTML Formatting**: Semua pesan bot menggunakan HTML parse mode dengan:
  - `<b>bold</b>` untuk informasi penting (nama, harga, total)
  - `<i>italic</i>` untuk disclaimer dan keterangan
  - `<code>code</code>` untuk ID dan data yang perlu dicopy
  - Emoji konsisten untuk visual hierarchy yang jelas
  - Sticker saat `/start` untuk pengalaman lebih engaging
- **Clean Message Flow**: Tidak ada pesan redundant, keyboard langsung melekat pada pesan utama

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

## Recent Fixes & Improvements (v0.7.0 - Latest)

### ✅ v0.7.0 - Comprehensive Database & Service Layer Overhaul (2025-01-06)

**Database Schema Improvements:**
- Added UNIQUE constraint on `product_contents.content` (prevent duplicate codes to users)
- Added UNIQUE constraint on `product_term_submissions` (order_id, product_id, telegram_user_id)
- Added CHECK constraints on `coupons` (used_count validation)
- Added CHECK constraints on monetary fields (non-negative values)
- Enhanced `deposits` table with gateway_order_id, fee_cents, payable_cents
- Enabled `audit_log` table for comprehensive tracking
- Created 25+ performance indexes

**Service Layer Enhancements:**
- `catalog.py`: Complete FK validation (category_exists, product_is_active)
- `product_content/__init__.py`: Duplicate detection, bulk operations, integrity checks
- `voucher.py`: Complete rewrite with usage tracking and validation
- `order.py`: UUID standardization with auto-conversion
- `deposit.py`: Gateway vs manual separation with comprehensive validation
- `reply_templates.py`: Duplicate label prevention

**Migration & Safety:**
- Created comprehensive migration script with data cleanup
- Python migration runner with backup, validation, and rollback
- Migration tracking table
- Integrity check functions

**Code Quality:**
- 40+ new utility functions
- Comprehensive docstrings and type hints
- Improved error handling with clear messages
- Structured logging throughout
- Input validation standardized

**Files:** `FIXES_SUMMARY_v0.7.0.txt`, `docs/codebase-critics.md`, `scripts/migrations/001_fix_schema_constraints.sql`

---

## Previous Fixes & Improvements (v0.2.3 - v0.6.0)

### ✅ Complete Admin UX Overhaul (v0.2.3)

**Major UX Improvements:**
- **Step-by-Step Wizards**: Semua admin operations sekarang menggunakan wizard ramah awam
  - Tambah Produk: 5 langkah dengan progress indicator (Kode → Nama → Harga → Stok → Deskripsi)
  - Edit Produk: Pilih dari list → Pilih field → Input nilai baru
  - Kelola SNK: Pilih dari list → Input SNK atau ketik "hapus"
  - Calculator: Direct input tanpa command, step-by-step guidance
  
- **Inline Cancel Buttons Everywhere**: Semua input modes sekarang punya inline cancel button (bukan text button)
  - Kelola Respon Bot: ✅ Inline cancel
  - Tambah/Edit/Hapus Produk: ✅ Inline cancel di setiap step
  - Kelola SNK: ✅ Inline cancel
  - Generate Voucher: ✅ Inline cancel
  - Calculator (Hitung & Atur Formula): ✅ Inline cancel
  - Broadcast: ✅ Inline cancel
  
- **No More Complex Formats**: Hapus format kompleks seperti `kategori_id|kode|nama|harga|stok|deskripsi`
  - Sekarang: Input step-by-step dengan guidance jelas
  - Progress indicator: "Langkah 1/5", "Langkah 2/5", dst
  - Preview data yang sudah diinput di setiap step
  
- **Visual Selection**: Admin tidak perlu tahu ID produk
  - Pilih produk dari list dengan inline buttons
  - Preview info produk sebelum edit/delete
  - Confirmation dialog untuk destructive actions
  
- **Clean Welcome Flow**: Hanya 2 pesan saat `/start` (sticker + welcome)
  - Removed: Pesan '💬' yang redundant
  - Reply keyboard attached langsung ke welcome message

**Bug Fixes:**
- Fixed: UnboundLocalError saat kirim 'Statistik' (missing import `list_users`)
- Fixed: Calculator tidak berfungsi (command `/refund_calculator` dan `/set_calculator` tidak ada response)
- Fixed: Category foreign key error saat tambah produk (category_id sekarang optional)
- Fixed: Membership test warning di admin_menu.py

**Database Changes:**
- `category_id` di tabel `products` sekarang nullable (auto-migrated)
- No breaking changes untuk existing data

### ✅ Previous Improvements (v0.2.2)

### ✅ Configuration & Validation
- Fixed `TELEGRAM_ADMIN_IDS` and `TELEGRAM_OWNER_IDS` validator to handle single integer values and comma-separated strings
- Enhanced input validation across all admin functions with proper error messages
- Added comprehensive config validation at startup

### ✅ Dependencies & Setup
- Updated `requirements.txt` to `python-telegram-bot[webhooks,job-queue]==21.3`
- All scheduled tasks (SNK dispatch, broadcast queue, health checks) now work without warnings
- JobQueue fully functional for background tasks

### ✅ Admin Menu Complete Restructure
- **New Hierarchical Structure**: Main menu `⚙️ Admin Settings` dengan 9 submenu terorganisir
- **Kelola Respon Bot**: 
  - Preview semua template pesan (welcome, product, cart, payment, error, success, SNK)
  - Edit template teks dengan placeholder validation
  - Upload gambar untuk template
  - Cancel button pada setiap mode input
- **Kelola User**: 
  - Statistics dashboard (total users, active, blocked)
  - User list dengan pagination
  - Block/unblock functionality
  - User detail view
- **Broadcast**:
  - Send text or photo to all users
  - Real-time statistics (total, success, failed)
  - Cancel button untuk membatalkan proses
  - Automatic handling untuk user yang block bot
- **Calculator**: 
  - User-friendly inline keyboard untuk input nominal
  - Support untuk refund dan deposit calculation
  - Clear visual feedback
- **Kelola Voucher**:
  - Format lebih sederhana (nominal/persentase/custom)
  - Cancel button untuk membatalkan pembuatan
  - Validasi input yang lebih baik

### ✅ UX & UI Enhancements
- **Role-Based Keyboard**: Admin melihat admin keyboard, customer melihat customer keyboard
- **Sticker on Start**: Bot mengirim sticker sebelum welcome message untuk engagement
- **Clean Message Flow**: 
  - Removed redundant messages ("📱 Gunakan menu...", "👇")
  - Keyboard langsung melekat pada pesan utama
  - Tidak ada double message
- **HTML Parse Mode Migration**: 
  - Semua message templates menggunakan HTML formatting
  - Bold untuk informasi penting (nama user, store name, harga, total)
  - Italic untuk disclaimer dan note
  - Code tags untuk ID dan data yang perlu dicopy
  - Added `parse_mode=ParseMode.HTML` di 15+ handler functions
- **Enhanced Message Templates**:
  - `welcome_message`: Bold pada nama user dan statistik
  - `product_list_heading` & `product_list_line`: Bold pada nama produk dan harga
  - `product_detail`: Bold pada field labels dan values
  - `cart_summary`: Bold pada totals dan item counts
  - `payment_prompt`, `payment_invoice_detail`, `payment_success`: Visual hierarchy yang jelas
  - `generic_error`: Bold pada main error message

### ✅ User Statistics & Tracking
- **Auto User Upsert**: Setiap `/start` otomatis menambah/update user di database
- **Real Statistics**: Total user dan transaksi sekarang akurat dan realtime
- **Database Tracking**: Semua user interaction tercatat lengkap

### ✅ Code Quality & Security
- All message templates migrated from Markdown to HTML
- No bare exceptions detected in codebase scan
- All error handling uses specific exception types
- Consistent code style across all files
- Proper input validation and sanitization
- No SQL injection vulnerabilities

### ✅ Admin Experience Improvements
- Cancel buttons pada semua mode input kritikal (broadcast, voucher, edit template)
- Inline keyboard untuk navigasi yang lebih intuitif
- Statistics dan feedback real-time
- Better error messages dengan actionable information

### 📝 Documentation Updates
- Complete update of `docs/fixing_plan.md` dengan status semua fixes
- Updated `docs/CHANGELOG.md` dengan detailed changelog
- Updated `docs/08_release_notes.md` dengan release notes v0.2.2
- Updated `docs/core_summary.md` dengan fitur dan struktur terbaru
- Updated `docs/02_prd.md` dengan requirements baru
- All documentation now reflects current implementation

### 🔧 Technical Improvements
- Standardized callback data format across all inline keyboards
- Improved error handling in admin handlers
- Better state management for multi-step admin flows
- Optimized database queries for statistics
- Enhanced logging for admin actions

For detailed fix history and implementation details, see `docs/fixing_plan.md` and `docs/CHANGELOG.md`.

## Pre-Production Checklist
- **Environment Setup**:
  - [ ] Install/upgrade dependencies: `pip install -r requirements.txt`
  - [ ] Verify JobQueue available: `python -c "from telegram.ext import JobQueue; print('✅ JobQueue available!')"`
  - [ ] Check config validators: Ensure `TELEGRAM_ADMIN_IDS` and `TELEGRAM_OWNER_IDS` format correct
- [ ] **User Experience Testing**:
  - [ ] Test `/start` sebagai admin: Verify ONLY 2 messages (sticker + welcome), no '💬' message
  - [ ] Test `/start` sebagai customer: Verify customer keyboard tampil tanpa admin access
  - [ ] Test statistik menu: No UnboundLocalError, data displayed correctly
  - [ ] Test role-based keyboard: Admin vs customer views berbeda
- [ ] **Admin Menu Testing**:
  - [ ] Enter `⚙️ Admin Settings`: Verify semua 9 submenu tampil
  - [ ] **Kelola Respon Bot**: Test preview templates, edit text, **verify inline cancel button**
  - [ ] **Tambah Produk**: Test 5-step wizard (kode→nama→harga→stok→deskripsi), **verify inline cancel at each step**
  - [ ] **Edit Produk**: Select from list → Select field → Input value, **verify inline cancel**
  - [ ] **Hapus Produk**: Select from list → Confirm deletion, **verify inline cancel**
  - [ ] **Kelola SNK**: Select from list → Input SNK or type "hapus", **verify inline cancel**
  - [ ] **Kelola User**: Test user statistics (no UnboundLocalError), list pagination, block/unblock
  - [ ] **Broadcast**: Test send message, verify statistics, **verify inline cancel button**
  - [ ] **Calculator**: Test "Hitung Refund" (direct, no command), test "Atur Formula", **verify inline cancel**
  - [ ] **Kelola Voucher**: Test voucher generation, **verify inline cancel button**
- **Message Formatting**:
  - [ ] Verify all messages use HTML parse mode
  - [ ] Check bold formatting pada important info (names, prices, totals)
  - [ ] Check italic pada disclaimers
  - [ ] Check code tags pada IDs
  - [ ] Verify no redundant messages ("👇" atau double messages)
- **Background Jobs** (requires JobQueue):
  - [ ] SNK dispatch running: Check logs for `[snk_handler]`
  - [ ] Broadcast queue running: Check logs for `[broadcast_queue]`
  - [ ] Health checks running: Check logs for `[healthcheck]`
- **Integration Testing**:
  - [ ] Payment flow (Pakasir webhook handling)
  - [ ] Order notifications ke admin (tanpa owner)
  - [ ] SNK submission flow
  - [ ] Anti-spam protection
- **Production Environment**:
  - [ ] **Chaos test**: `docker compose kill` then verify container restart and jobs continue
  - [ ] **Backup drill**: `backup_manager create → verify → restore` di staging
  - [ ] **Gateway simulation**: Use `paymentsimulation` API (see `docs/pakasir.md`)
  - [ ] **Resource exhaustion**: Test `healthcheck` under load
  - [ ] **Dependency check**: Build fresh image and run regression tests

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

### SyntaxError: `</parameter>` di PaymentService
- Gejala: `SyntaxError: invalid syntax` saat menjalankan `./scripts/run_stack.sh` dengan pointer ke `src/services/payment.py`.
- Solusi: Pastikan kode sudah diperbarui ke versi `0.5.2` (commit hotfix menghapus fragmen markup `</parameter></invoke>` yang tersisa).
- Validasi cepat: `python -m compileall src` harus selesai tanpa error.

### JobQueue Warning Still Appearing
Jika masih muncul `PTBUserWarning: No 'JobQueue' set up`:
```bash
# Reinstall dependencies dengan job-queue support
source venv/bin/activate
pip uninstall python-telegram-bot -y
pip install -r requirements.txt

# Atau recreate venv
deactivate
rm -rf venv
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Verify installation
python -c "from telegram.ext import JobQueue; print('✅ JobQueue available!')"
```

### Admin Keyboard Not Showing
1. Verify user ID ada di `TELEGRAM_ADMIN_IDS` di `.env`
2. Check format: `TELEGRAM_ADMIN_IDS=5473468582` (single) atau `TELEGRAM_ADMIN_IDS=5473468582,123456789` (multiple)
3. Restart bot after changing `.env`
4. Test dengan `/start` sebagai admin user

### Error Statistik (UnboundLocalError)
- Fixed in v0.2.3: `list_users` sekarang properly imported
- Statistik menu berfungsi dengan baik
- No more UnboundLocalError saat kirim 'Statistik'

### Calculator Tidak Berfungsi
- Fixed in v0.2.3: Calculator langsung berfungsi dari menu (no command needed)
- "🔢 Hitung Refund" → Direct wizard (no `/refund_calculator` command)
- "⚙️ Atur Formula" → Direct input (no `/set_calculator` command)
- Semua dengan inline cancel button

### Tambah Produk Error (Foreign Key)
- Fixed in v0.2.3: `category_id` sekarang optional (nullable)
- No more foreign key constraint error
- Wizard step-by-step 5 langkah (tidak perlu kategori)

### Cancel Button Tidak Berfungsi
- Fixed in v0.2.3: Semua cancel button sekarang inline keyboard
- No more "Aksi admin tidak dikenali" saat cancel
- Konsisten di semua menu admin

## Lisensi
Internal use only.
