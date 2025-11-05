bot-auto-order/docs/08_release_notes.md
# 📝 Release Notes – Bot Auto Order Telegram

Dokumen ini mencatat perubahan penting, penambahan fitur, bugfix, refactor, dan issue yang masih terbuka pada proyek bot auto order Telegram.

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
