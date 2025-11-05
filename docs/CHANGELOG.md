bot-auto-order/docs/CHANGELOG.md
# 📝 Changelog – Bot Auto Order Telegram

Dokumen ini mencatat riwayat perubahan, penambahan fitur, bugfix, refactor, dan milestone penting pada proyek bot auto order Telegram. Format mengikuti best practice changelog agar mudah diaudit dan diikuti oleh tim/AI builder berikutnya.

---

## [0.2.1] – 2025-11-05
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

## [0.2.0] – 2025-11-01
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

## [0.1.0] – 2025-11-01
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
