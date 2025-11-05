bot-auto-order/docs/CHANGELOG.md
# 📝 Changelog – Bot Auto Order Telegram

Dokumen ini mencatat riwayat perubahan, penambahan fitur, bugfix, refactor, dan milestone penting pada proyek bot auto order Telegram. Format mengikuti best practice changelog agar mudah diaudit dan diikuti oleh tim/AI builder berikutnya.

---

## [0.2.2] – 2025-01-16 (Major UX & Admin Menu Overhaul)

### Added
- **Role-Based Keyboard System**: Bot sekarang menampilkan keyboard berbeda berdasarkan role user
  - Admin users: Melihat `⚙️ Admin Settings` button untuk akses penuh ke admin menu
  - Customer users: Melihat customer keyboard standar tanpa akses admin features
  - Automatic role detection berdasarkan `TELEGRAM_ADMIN_IDS`
- **Complete Admin Menu Restructure**: Menu admin sekarang terorganisir dalam hierarki dengan 9 submenu:
  - **⚙️ Admin Settings** (main menu) dengan submenu:
    - 📝 **Kelola Respon Bot**: Preview dan edit template messages (welcome, product, cart, payment, error, success, SNK)
    - 📦 **Kelola Produk**: CRUD products dengan statistics lengkap
    - 📋 **Kelola Order**: View dan update order status
    - 👥 **Kelola User**: User statistics, list dengan pagination, block/unblock functionality
    - 🎟️ **Kelola Voucher**: Generate vouchers dengan format user-friendly (nominal/persentase/custom)
    - 📢 **Broadcast**: Send messages (text/photo) ke semua users dengan real-time statistics
    - 🧮 **Calculator**: User-friendly calculator untuk refund/deposit dengan inline keyboard
    - 📊 **Statistik**: Comprehensive dashboard dengan bot metrics
    - 💰 **Deposit**: Manage user deposits dengan inline buttons
- **Cancel Buttons**: Added cancel functionality untuk semua critical input modes:
  - Broadcast message composition
  - Voucher generation
  - Template editing
  - Calculator input
  - User dapat cancel operation kapanpun dengan tombol `❌ Cancel`
- **Sticker on Welcome**: Bot sekarang mengirim sticker engaging sebelum welcome message untuk better user experience
- **Auto User Tracking**: Setiap `/start` command otomatis menjalankan `upsert_user()` untuk accurate statistics tracking
- **Inline Keyboard Navigation**: Admin menu menggunakan inline keyboards untuk navigasi yang lebih intuitif dan clean
- **Real-Time Statistics**: Broadcast dan admin operations menampilkan real-time feedback (total, success, failed counts)

### Fixed
- **Config Validator**: Fixed `TELEGRAM_ADMIN_IDS` and `TELEGRAM_OWNER_IDS` validators di `src/core/config.py` untuk handle:
  - Single integer values (e.g., `123456789`)
  - Comma-separated strings (e.g., `123456789,987654321`)
  - Proper validation dengan error messages yang jelas
- **JobQueue Warning**: Updated `requirements.txt` ke `python-telegram-bot[webhooks,job-queue]==21.3` untuk enable scheduled tasks tanpa warnings:
  - SNK dispatch jobs
  - Broadcast queue processing
  - Health check scheduler
  - Auto backup scheduler
- **User Statistics Not Counting**: Fixed issue dimana user count tidak bertambah saat `/start`:
  - Added `upsert_user()` call di `start()` handler
  - Setiap new user atau existing user otomatis tracked di database
  - Statistics sekarang accurate dan real-time
- **Redundant Messages**: Removed redundant messages yang mengganggu UX:
  - Removed "📱 Gunakan menu di bawah..." message
  - Removed standalone "👇" message
  - Keyboard sekarang langsung attached ke welcome message
- **Admin Keyboard Not Showing**: Fixed issue dimana admin tidak melihat admin keyboard saat `/start`:
  - Implemented proper role detection
  - Admin keyboard (`⚙️ Admin Settings`) sekarang muncul untuk semua admin users
  - Customer keyboard tampil untuk non-admin users
- **Calculator Access Control**: Removed "🧮 Calculator" button dari customer reply keyboard (now admin-only via commands `/refund_calculator` and `/set_calculator`)
- **Empty Admin Menus**: Fully implemented semua admin submenu yang sebelumnya empty:
  - Kelola Respon Bot: Complete dengan preview, edit, upload image features
  - Kelola User: Complete dengan statistics, pagination, block/unblock
  - Broadcast: Complete dengan statistics dan error handling
  - Calculator: Complete dengan inline keyboard input
  - Voucher: Complete dengan improved format dan validation

### Changed
- **HTML Parse Mode Migration**: Migrated ALL message templates dari Markdown ke HTML parse mode:
  - **Bold formatting** (`<b>tags</b>`) untuk important information: user names, store name, prices, totals, field labels
  - **Italic formatting** (`<i>tags</i>`) untuk disclaimers, notes, dan keterangan tambahan
  - **Code formatting** (`<code>tags</code>`) untuk IDs dan data yang perlu di-copy (invoice IDs, transaction IDs)
  - Consistent emoji usage untuk visual hierarchy
  - Added `parse_mode=ParseMode.HTML` di 15+ handler functions
- **Enhanced Message Templates** di `src/bot/messages.py`:
  - `welcome_message`: Bold pada user name, store name, dan statistics (Total Pengguna, Transaksi Tuntas)
  - `product_list_heading` & `product_list_line`: Bold pada product names, prices, dan quantities
  - `product_detail`: Bold pada field labels (Nama, Harga, Stok, Kategori) dan values
  - `cart_summary`: Bold pada totals, item counts, dan subtotals
  - `payment_prompt`: Bold pada payment method selection
  - `payment_invoice_detail`: Bold pada invoice ID, amount, dan payment instructions
  - `payment_success`: Bold pada success message dan order details
  - `generic_error`: Bold pada main error message untuk visibility
- **Handler Updates** di `src/bot/handlers.py`:
  - `start()`: Combined welcome text dengan inline keyboard di first message, no double messages
  - `handle_product_list()`: Product listings dengan proper HTML formatting
  - `show_product_detail()`: Product detail cards dengan bold labels
  - `callback_router()`: All callback responses menggunakan HTML parse mode
  - `text_router()`: Generic error messages dengan HTML formatting
- **Admin Handlers Refactor** di `src/bot/admin/`:
  - Standardized callback data format across all inline keyboards
  - Improved error handling dengan specific exception types
  - Better state management untuk multi-step admin flows
  - Enhanced logging untuk all admin actions
  - Optimized database queries untuk statistics
- **Voucher System Improvement**:
  - Simplified voucher generation format (nominal/persentase/custom text)
  - Added cancel button untuk abort voucher creation
  - Better input validation dan error messages
  - User-friendly prompts dan instructions
- **Broadcast System Enhancement**:
  - Real-time statistics display (total users, successful sends, failed sends)
  - Automatic handling untuk users yang block bot
  - Cancel button untuk abort broadcast mid-process
  - Improved error handling dan logging
  - Support untuk text dan photo broadcasts
- **User Management Enhancement**:
  - Added user statistics dashboard (total, active, blocked)
  - Pagination untuk user lists
  - Block/unblock functionality dengan confirmation
  - User detail view dengan transaction history
  - Navigation buttons untuk better UX
- **Clean Message Flow**:
  - Single message untuk welcome + keyboard (no double messages)
  - Removed semua redundant helper messages
  - Streamlined conversation flow
  - Better visual hierarchy dengan HTML formatting

### Documentation
- **README.md**: Complete overhaul dengan:
  - Updated features list dengan role-based keyboard dan admin menu structure
  - Added comprehensive Pre-Production Checklist dengan detailed testing steps
  - Enhanced Troubleshooting section dengan JobQueue, admin keyboard, dan statistics issues
  - Updated Recent Fixes section dengan detailed changelog
  - Added installation verification steps
- **docs/fixing_plan.md**: Comprehensive update dengan:
  - Status semua fixes marked dengan ✅
  - Summary table dengan all issues dan resolutions
  - File references untuk each fix
  - Testing verification checklist
  - Implementation details untuk major changes
- **docs/CHANGELOG.md**: This file - detailed changelog untuk v0.2.2
- **docs/08_release_notes.md**: Updated dengan release notes untuk v0.2.2
- **docs/core_summary.md**: Updated dengan current features dan module status
- **docs/02_prd.md**: Updated requirements untuk reflect new features
- All documentation sekarang reflects current implementation state

### Code Quality
- **No Bare Exceptions**: All error handling uses specific exception types (ValueError, KeyError, etc.)
- **No SQL Injection**: Proper parameterized queries throughout codebase
- **Consistent Code Style**: Standardized formatting across all modified files
- **Comprehensive Error Handling**: Proper try-catch blocks dengan informative error messages
- **Input Validation**: All admin inputs validated sebelum processing
- **Security**: Proper role-based access control untuk all admin features
- **Logging**: Enhanced logging untuk debugging dan audit purposes
- **Type Safety**: Proper type hints where applicable
- **Code Deduplication**: Refactored common patterns into reusable functions

### Performance
- **Optimized Database Queries**: Better query structure untuk statistics dan user lists
- **Efficient Message Handling**: Reduced redundant API calls
- **Smart Caching**: Better state management reduces unnecessary database hits

### Known Issues
- Port conflicts (9000, 8080) require manual resolution sebelum deployment
- JobQueue requires dependency reinstall di existing installations (see Troubleshooting in README)
- Large broadcast operations (>1000 users) mungkin memerlukan rate limiting tuning

### Migration Notes
Untuk upgrade dari v0.2.1+ ke v0.2.2:
1. **Update Dependencies**:
   ```bash
   pip uninstall python-telegram-bot -y
   pip install -r requirements.txt
   python -c "from telegram.ext import JobQueue; print('✅ JobQueue available!')"
   ```
2. **Database**: No schema changes required
3. **Configuration**: Verify `TELEGRAM_ADMIN_IDS` format di `.env` (supports single or comma-separated)
4. **Testing**: Run through Pre-Production Checklist di README.md
5. **Restart**: Restart bot untuk load new code dan dependencies

---

## [0.2.1+] – 2025-01-15 (Hotfix - DEPRECATED, See 0.2.2)
### Fixed
- **Config Validator**: Fixed `TELEGRAM_ADMIN_IDS` and `TELEGRAM_OWNER_IDS` validators in `src/core/config.py` to handle single integer values (not just comma-separated strings)
- **JobQueue Warning**: Updated `requirements.txt` to include `python-telegram-bot[webhooks,job-queue]==21.3` to enable scheduled tasks without warnings
- **Calculator Access Control**: Removed "🧮 Calculator" button from customer reply keyboard (now admin-only via `/refund_calculator` and `/set_calculator` commands)

### Changed
- **UX/UI Improvements**: Migrated all message templates from Markdown to HTML parse mode
  - Welcome message now shows inline keyboard in first message with better formatting
  - All important information now uses `<b>bold</b>` tags for emphasis
  - Disclaimers use `<i>italic</i>` formatting
  - Invoice IDs and transaction IDs use `<code>` tags for copy-paste
  - Added `parse_mode=ParseMode.HTML` consistently across 10+ handler functions
- **Message Templates**: Enhanced all messages in `src/bot/messages.py` with proper HTML formatting:
  - `welcome_message`: Bold on user name, store name, and statistics
  - `product_list_heading` and `product_list_line`: Bold on product names, prices, and quantities
  - `product_detail`: Bold on field labels and values
  - `cart_summary`: Bold on totals and item counts
  - `payment_prompt`, `payment_invoice_detail`, `payment_success`: Enhanced visual hierarchy
  - `generic_error`: Bold on main error message
- **Handler Updates**: Updated `src/bot/handlers.py` to consistently use HTML parse mode in:
  - `start()`: Combined welcome text with inline keyboard in first message
  - `handle_product_list()`: Product listings with HTML formatting
  - `show_product_detail()`: Product detail cards
  - `callback_router()`: All callback responses (cart, payment, product selection)
  - `text_router()`: Generic error messages

### Documentation
- **README.md**: Added recent fixes section, troubleshooting guide, and testing checklist
- **fixing_plan.md**: Comprehensive update with status of all fixes, marked completed items with ✅
- Added summary table of all fixes with file references
- Documented testing checklist for post-deployment verification

### Code Quality
- No bare exceptions or SQL injection vulnerabilities detected in codebase scan
- All error handling uses specific exception types
- Consistent code style throughout all modified files

### Known Issues
- Port conflicts (9000, 8080) require manual resolution before deployment
- Signal handling relies on python-telegram-bot library defaults (no custom implementation needed)

---

## [0.2.1] – 2025-06-05
### Added
- Mode `auto` untuk failover polling/webhook (`src/main.py`, `scripts/run_stack.sh`) beserta panduan switch DNS/Reverse Proxy.
- CLI `src/tools/healthcheck.py` untuk pengecekan Telegram API, Postgres, dan disk dengan alert ke owner.
- Dockerfile + template Compose untuk multi-tenant deployment dengan restart policy.
- Enkripsi SNK + purge otomatis (`DATA_ENCRYPTION_KEY`, `SNK_RETENTION_DAYS`) dan backup manager terenkripsi.
- Broadcast queue persisten dengan dispatcher terjadwal dan audit log.
### Changed
- Pengiriman SNK memakai PostgreSQL advisory lock (`src/services/locks.py`) agar aman pada multi-instance.
- README diperbarui dengan instruksi failover, health-check, dan Docker.
- Health-check menambah CPU/RAM/log usage; PaymentService mengirim alert saat kegagalan beruntun, OwnerAlertHandler menyalurkan log level tinggi.
- Docker image kini menggunakan multi-stage build (lebih ringan) dan disertai skrip `cron_healthcheck.sh`/`cron_backup.sh` untuk automasi tenant.
- Skrip `provision_tenant.py` mempermudah pembuatan struktur `deployments/bot-<store>-<gateway>` secara otomatis.
- Scheduler internal menjalankan health-check & backup otomatis berdasarkan env (`ENABLE_AUTO_HEALTHCHECK`, `HEALTHCHECK_INTERVAL_MINUTES`, `ENABLE_AUTO_BACKUP`, `BACKUP_TIME`).
### Known Issues
- Jalankan health-check di environment yang sudah menginstal dependency (`pip install -r requirements.txt`) dan memiliki koneksi Postgres.

---

## [0.2.0] – 2025-06-01
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

## [0.1.0] – 2025-05-01
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

> Semua perubahan, bugfix, dan milestone wajib didokumentasikan di sini sebelum deploy ke production.
> Untuk perubahan besar, sertakan referensi ke dokumen terkait di folder `docs/`.
