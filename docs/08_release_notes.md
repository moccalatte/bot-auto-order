bot-auto-order/docs/08_release_notes.md
# 📝 Release Notes – Bot Auto Order Telegram

Dokumen ini mencatat perubahan penting, penambahan fitur, bugfix, refactor, dan issue yang masih terbuka pada proyek bot auto order Telegram.

---

## Version 0.2.3 – 2025-01-16
### Added
- **Step-by-Step Wizards for All Admin Operations**: Complete refactor menjadi user-friendly wizards
  - Tambah Produk: 5-langkah wizard (Kode → Nama → Harga → Stok → Deskripsi) dengan progress indicator
  - Edit Produk: Visual selection dari list → Pilih field → Input nilai baru
  - Hapus Produk: Visual selection → Confirmation dialog dengan preview
  - Kelola SNK: Visual selection → Input SNK atau ketik "hapus"
  - Calculator: Direct wizard tanpa command, step-by-step guidance
- **Inline Cancel Buttons Everywhere**: Semua admin operations sekarang punya inline cancel button
  - All 10+ admin menus: Edit templates, Tambah/Edit/Hapus Produk, SNK, Voucher, Calculator, Broadcast
  - One-click cancel functionality
  - Consistent UX across all menus
- **Visual Product Selection**: Admin tidak perlu tahu product_id lagi
  - Inline buttons dengan list produk (nama + harga)
  - Preview info sebelum edit/delete
  - Confirmation dialogs untuk destructive actions
- **Progress Indicators**: "Langkah X/Y" di multi-step operations dengan preview data yang sudah diinput

### Fixed
- **Error Statistik**: Fixed UnboundLocalError (missing `list_users` import) yang menyebabkan crash saat kirim 'Statistik'
- **Calculator Tidak Berfungsi**: Menu Calculator sekarang langsung start wizard, no more commands `/refund_calculator` atau `/set_calculator`
- **Pesan '💬' Redundant**: Removed pesan '💬' saat `/start`, now only 2 messages (sticker + welcome)
- **Category Foreign Key Error**: Made `category_id` nullable di products table, no more constraint errors
- **Cancel Button UX**: All cancel buttons changed from ReplyKeyboard to InlineKeyboard
- **Membership Test**: Fixed `not in` syntax warning di admin_menu.py

### Changed
- **No More Complex Formats**: Removed all complex input strings
  - Tambah Produk: `kategori_id|kode|nama|harga|stok|deskripsi` → 5-step wizard
  - Edit Produk: `produk_id|field=value` → Visual selection + simple input
  - Kelola SNK: `product_id|SNK baru` → Visual selection + text input
- **Category Optional**: Products no longer require category_id (nullable in database, auto-migrated)
- **Calculator Direct Integration**: Functions integrated directly to menu buttons (no commands needed)
- **Public Helper**: `parse_price_to_cents()` made public for reuse

### Database
- `category_id` in `products` table made nullable (auto-migrated)
- Backward compatible with existing data

### Migration Notes
1. Pull code: `git pull origin main`
2. Restart bot (auto-migration runs)
3. Test: Tambah Produk wizard, Calculator direct access, Cancel buttons

### Known Issues
- None - All 8 reported issues resolved ✅

---

## Version 0.2.2 – 2025-01-16
### Added
- **Role-Based Keyboard System**: Bot automatically displays different keyboards based on user role (admin vs customer)
- **Complete Admin Menu Restructure**: New hierarchical menu structure with `⚙️ Admin Settings` main menu and 9 organized submenus:
  - 📝 Kelola Respon Bot (preview & edit message templates)
  - 📦 Kelola Produk (CRUD with statistics)
  - 📋 Kelola Order (view & update status)
  - 👥 Kelola User (statistics, pagination, block/unblock)
  - 🎟️ Kelola Voucher (user-friendly generation)
  - 📢 Broadcast (send to all users with real-time stats)
  - 🧮 Calculator (inline keyboard for refund/deposit)
  - 📊 Statistik (comprehensive dashboard)
  - 💰 Deposit (manage user deposits)
- **Cancel Buttons**: Added cancel functionality for all critical input modes (broadcast, voucher, template editing, calculator)
- **Sticker on Welcome**: Engaging sticker sent before welcome message for better UX
- **Auto User Tracking**: Every `/start` command automatically runs `upsert_user()` for accurate statistics
- **Inline Keyboard Navigation**: Cleaner, more intuitive admin menu navigation
- **Real-Time Statistics**: Live feedback for broadcast operations (total, success, failed counts)

### Fixed
- **Config Validator**: Fixed `TELEGRAM_ADMIN_IDS` and `TELEGRAM_OWNER_IDS` validators to handle both single integers and comma-separated strings
- **JobQueue Warning**: Updated dependencies to `python-telegram-bot[webhooks,job-queue]==21.3` to eliminate warnings for scheduled tasks
- **User Statistics Not Counting**: Fixed issue where user count didn't increment on `/start` by adding automatic `upsert_user()` call
- **Redundant Messages**: Removed "📱 Gunakan menu..." and "👇" messages that cluttered conversation flow
- **Admin Keyboard Not Showing**: Implemented proper role detection so admin users see `⚙️ Admin Settings` button
- **Calculator Access Control**: Removed calculator from customer keyboard (admin-only via commands)
- **Empty Admin Menus**: Fully implemented all previously empty admin submenus with complete functionality

### Changed
- **HTML Parse Mode Migration**: Migrated ALL message templates from Markdown to HTML with:
  - `<b>bold</b>` for important info (names, prices, totals)
  - `<i>italic</i>` for disclaimers and notes
  - `<code>code</code>` for IDs and copyable data
  - Consistent emoji usage for visual hierarchy
- **Enhanced Message Templates**: Updated 10+ message templates in `src/bot/messages.py` with proper HTML formatting
- **Handler Updates**: Added `parse_mode=ParseMode.HTML` consistently across 15+ handler functions
- **Admin Handlers Refactor**: Standardized callback data format, improved error handling, better state management
- **Clean Message Flow**: Single welcome message with keyboard (no double messages), streamlined conversation flow

### Documentation
- Comprehensive update of README.md with new features, testing checklist, and troubleshooting
- Updated fixing_plan.md with complete fix status and implementation details
- Updated CHANGELOG.md with detailed v0.2.2 changelog
- Updated core_summary.md with current features and module status
- Updated PRD (02_prd.md) to reflect new requirements
- All documentation now reflects current implementation

### Code Quality
- No bare exceptions (all use specific exception types)
- No SQL injection vulnerabilities
- Comprehensive error handling with informative messages
- Proper input validation for all admin inputs
- Enhanced logging for debugging and audit
- Consistent code style across all files

### Known Issues
- Port conflicts (9000, 8080) require manual resolution before deployment
- JobQueue requires dependency reinstall in existing installations
- Large broadcast operations (>1000 users) may require rate limiting tuning

### Migration Notes
To upgrade from v0.2.1 to v0.2.2:
1. Update dependencies: `pip uninstall python-telegram-bot -y && pip install -r requirements.txt`
2. Verify JobQueue: `python -c "from telegram.ext import JobQueue; print('✅')"`
3. No database schema changes required
4. Verify `TELEGRAM_ADMIN_IDS` format in `.env`
5. Restart bot to load new code

---

## Version 0.2.1 – 2025-06-05
### Added
- Mode `auto` pada `src/main.py` dan `scripts/run_stack.sh` untuk failover webhook → polling tanpa downtime. Dokumentasi switch DNS/Reverse Proxy ditambahkan ke `docs/10_roadmap_critical.md`.
- CLI `python -m src.tools.healthcheck` yang menulis log ke `logs/health-check/` dan mengirim alert ke owner.
- Dockerfile + template Compose untuk multi-tenant deployment `deployments/bot-<store>-<gateway>` dengan restart policy.
- Enkripsi data SNK menggunakan `DATA_ENCRYPTION_KEY`, job purge otomatis (`SNK_RETENTION_DAYS`), serta backup manager terenkripsi dengan alert owner.
- Broadcast queue persisten (`broadcast_jobs`) dengan dispatcher terjadwal dan audit log.
- Skrip `scripts/provision_tenant.py` dan `scripts/run_tenant.sh` untuk provisioning + menjalankan tenant baru berbasis Docker Compose.
### Changed
- Job SNK (`process_pending_snk_notifications`) memakai PostgreSQL advisory lock (`src/services/locks.py`) agar aman di multi-instance.
- README diperbarui dengan instruksi failover, penggunaan health-check, dan orkestra Docker.
- Health-check kini memantau CPU/RAM/disk/log usage; owner alert handler + PaymentService failure counter mengirim notifikasi real-time.
- Docker image diperkecil dengan multi-stage build, serta tersedia `scripts/cron_healthcheck.sh` dan `scripts/cron_backup.sh` untuk automasi operasional.
- Skrip `scripts/provision_tenant.py` mempercepat pembuatan folder tenant Compose (logs/backups/env) untuk setup multi-store.
- Scheduler internal (job queue) sekarang menjalankan health-check (`ENABLE_AUTO_HEALTHCHECK`) dan backup harian (`ENABLE_AUTO_BACKUP`, `BACKUP_TIME`) tanpa perlu cron host.
### Known Issues
- Health-check memerlukan dependency `httpx` dan koneksi Postgres aktif; jalankan di lingkungan yang sudah menginstal `requirements.txt`.
- **Note:** This version has been superseded by v0.2.2 which includes major UX and admin menu improvements.

---

## Version 0.1.0 – 2025-05-01
### Added
- Inisialisasi struktur starterkit di folder `docs/`
- PRD, dev_protocol, dan context project bot auto order Telegram
- Fitur onboarding `/start` dengan emoji dan statistik user
- Navigasi produk via inline keyboard dan reply keyboard
- Detail produk, keranjang belanja, dan kupon
- Integrasi pembayaran QRIS via Pakasir API
- Admin tools: CRUD produk, kategori, template pesan, backup/restore konfigurasi
- SNK per produk dan submission bukti SNK oleh customer
- Broadcast pesan admin ke seluruh user aktif
- Logging interaksi, error, dan perubahan konfigurasi di folder `/logs/`
- Notifikasi pesanan baru ke seller/admin (owner dikecualikan)
- Anti-spam dan notifikasi stok menipis

### Fixed
- Validasi input admin pada template pesan event
- Penanganan error API Pakasir (fallback pesan ke user)
- Idempotensi webhook pembayaran
- Bug pada penanganan invoice kadaluarsa

### Changed
- Refactor struktur folder: semua dokumen dipindah ke `docs/`
- Penyesuaian format log dan audit agar sesuai dev_protocol
- Update dependensi utama di `requirements.txt` (python-telegram-bot, httpx, qrcode)

### Known Issues
- Fitur deposit saldo otomatis belum sepenuhnya stabil
- Kadang terjadi delay pada broadcast pesan ke user dengan jumlah besar
- Fitur rollback konfigurasi admin masih manual
- Belum ada dashboard analitik berbasis web

---

## Version 0.2.0 – 2025-06-01
### Added
- Health check & alert ke bot owner khusus notifikasi (token di env, info bot_store_name)
- Backup otomatis & offsite, monitoring integritas backup, SOP restore
- Distributed lock untuk job queue pada multi-instance VPS
- Audit log perubahan konfigurasi dan submission SNK
- Early warning pembayaran gagal beruntun ke owner

### Fixed
- Bug pada validasi placeholder template pesan admin
- Error handling pada broadcast jika user memblokir bot
- Penanganan duplikasi order pada webhook

### Changed
- Penyesuaian roadmap dan milestone di `docs/04_dev_tasks.md`
- Update security policy dan risk audit sesuai best practice starterkit
- Refactor modul logging agar lebih modular dan efisien

### Known Issues
- Monitoring resource (disk, memory, CPU) hanya aktif di VPS owner, belum ada alert threshold otomatis
- Fitur backup restore belum diuji pada skenario kehilangan total VPS
- Belum ada fitur multi-language pada template SNK

---

## Format Changelog

```
## [version] - YYYY-MM-DD
### Added
- Fitur baru

### Fixed
- Bug yang diperbaiki

### Changed
- Refactor, update dependency, perubahan struktur

### Known Issues
- Masalah yang masih terbuka
```

---

## Bug Report Sample

**Bug:** Broadcast gagal jika user memblokir bot  
**Log:** `/logs/bot-order/2025-06-01.log`  
**Status:** Sudah diperbaiki di versi 0.2.0

---

> Semua perubahan, bugfix, dan issue wajib didokumentasikan di sini sebelum deploy ke production.
> Untuk perubahan besar, sertakan referensi ke dokumen terkait di folder `docs/`.
