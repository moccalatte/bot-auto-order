# 🚨 Roadmap & Critical Steps – Bot Auto Order Telegram

Dokumen ini menggabungkan roadmap dan langkah-langkah fatal/critical yang wajib diterapkan sebelum bot auto order Telegram masuk produksi. Fokus pada pencegahan kegagalan besar, kehilangan data, downtime, keamanan, dan compliance. Semua item di bawah WAJIB selesai sebelum go-live. Fitur opsional/non-critical dapat ditambahkan setelah aplikasi stabil.

> **Update 6 Nov 2025:** Target kritis terbaru: pastikan normalisasi fee QRIS, alur deposit otomatis, dan pembersihan pesan kadaluarsa telah diverifikasi di staging sebelum produksi. Tambahkan monitoring manual minimal saat upgrade karena perubahan menyentuh `PaymentService` & scheduler.

---

## 1. Infrastruktur & Ketahanan Server

- [x] Implementasi failover: mode polling + webhook, dokumentasi prosedur switch DNS/Reverse Proxy.  
  `src/main.py` kini mendukung `--mode auto` dan env `TELEGRAM_MODE`. Mode `auto` mencoba webhook terlebih dahulu (menggunakan `TELEGRAM_WEBHOOK_URL`) dan otomatis fallback ke polling bila webhook gagal/URL kosong. Prosedur switch:
  1. Update DNS/Reverse Proxy untuk mengarahkan endpoint Telegram baru.
  2. Set `TELEGRAM_MODE=webhook` dan `TELEGRAM_WEBHOOK_URL=https://domain-baru/telegram`.
  3. Jalankan `docker compose -f deployments/bot-<store>/compose.yml up -d --force-recreate` setelah propagasi.
  4. Jika webhook bermasalah, cukup ubah `TELEGRAM_MODE=polling` di `bot.env` dan restart container; bot tetap online tanpa downtime panjang.
- [x] Skrip health-check otomatis untuk mendeteksi downtime dan alert ke bot owner khusus notifikasi.  
  `python -m src.tools.healthcheck` memverifikasi Telegram API, Postgres, dan kapasitas disk, menulis log ke `logs/health-check/<tanggal>.log`, serta mengirim alert ke owner (menggunakan `TELEGRAM_OWNER_IDS`). Contoh hasil ada di `logs/health-check/sample.log`. Jadwalkan via cron, systemd timer, atau job scheduler container setiap 5 menit.
- [x] Orkestrasi Docker dengan restart policy agar bot auto-restart jika crash.  
  `Dockerfile` + `docker-compose.template.yml` menjalankan container menggunakan skrip `scripts/run_stack.sh`. Compose memakai `restart: always`, sehingga instance otomatis hidup ulang tanpa intervensi. Untuk multi-tenant, duplikasi folder `deployments/bot-<store>-<gateway>` dan jalankan `docker compose up -d`.
- [x] Uji chaos: matikan proses bot secara paksa, pastikan auto-restart dan job queue tetap utuh.  
  Langkah uji:
  1. Jalankan tenant via Docker Compose (`docker compose up -d`).
  2. Paksa crash: `docker compose kill`, atau `docker kill <container>` dengan sinyal `SIGKILL`.
  3. Verifikasi auto-restart: `docker compose ps` harus menunjukkan container hidup kembali <10 detik (status `running`).
  4. Pastikan antrian SNK tetap utuh: cek `SELECT COUNT(*) FROM product_term_notifications WHERE sent_at IS NULL;` sebelum & sesudah chaos; jumlah harus konsisten.
  5. Catat hasil di log maintenance.
- [x] Distributed lock untuk job queue pada multi-instance/standby VPS.  
  `process_pending_snk_notifications` kini memakai `src/services/locks.py` (Postgres advisory lock) sehingga hanya satu instance yang mengirim SNK sekaligus.

---

## 2. Backup & Restore

- [x] Backup otomatis dan terenkripsi untuk database, .env, konfigurasi, dan log.  
  Jalankan `python -m src.tools.backup_manager create` untuk membuat dump Postgres dengan `pg_dump`, mengarsipkan konfigurasi/log, dan mengenkripsi hasilnya (AES-256, OpenSSL). Output disimpan di `BACKUP_LOCAL_DIR` (default `backups/local/`). Scheduler internal menjalankan proses ini otomatis pada `BACKUP_TIME` ketika `ENABLE_AUTO_BACKUP=true`.
- [x] Backup offsite (cloud/remote server) untuk mitigasi kehilangan total VPS.  
  Gunakan flag `--offsite` agar arsip dan metadata otomatis tersalin ke `BACKUP_OFFSITE_DIR` (mount storage remote via NFS/SFTP/rclone sebelum eksekusi).
- [x] Monitoring integritas backup: alert ke bot owner jika backup gagal/corrupt.  
  Skrip menghitung hash SHA-256 dan menyimpan metadata `.meta.json`. Gagal/sukses dicatat di `logs/maintenance/` dan dikirim ke owner via `notify_owners`.
- [x] Uji restore berkala dari backup lokal dan offsite, pastikan data konsisten dan SOP mudah diikuti.  
  Perintah `python -m src.tools.backup_manager restore <file>` mendekripsi arsip, menjalankan `pg_restore --clean`, dan memulihkan file konfigurasi. Contoh log disediakan di `logs/maintenance/backup-sample.log`. Pastikan hasil verifikasi dicatat.
- [x] Terapkan versioning & retention policy agar backup tidak menumpuk dan mudah diakses saat recovery.  
  Gunakan `python -m src.tools.backup_manager prune --keep {N}` untuk menyisakan backup terbaru. Metadata timestamp + checksum membantu audit/penyortiran.

---

## 3. Job Queue & Data Integrity

- [x] Pastikan job queue (SNK pending, broadcast) persisten dan tidak hilang saat restart/crash.  
  SNK sudah menggunakan tabel `product_term_notifications`. Broadcast kini memanfaatkan `broadcast_jobs` + `broadcast_job_targets` dengan status `pending/processing/sent/failed`; dispatcher `process_broadcast_queue` berjalan periodik dan saat dijalankan ulang akan meneruskan sisa target.
- [x] Validasi idempotensi pada penjadwalan job agar tidak terjadi duplikasi atau kehilangan notifikasi.  
  `create_broadcast_job` menerapkan `UNIQUE(job_id, telegram_id)` sehingga target tidak ganda, sedangkan SNK menjaga idempotensi via `UNIQUE (order_id, product_id)`. Lock distributed (SNK) dan status `processing` memastikan hanya satu worker mengirim tiap target.
- [x] Audit log untuk setiap perubahan dan eksekusi job critical.  
  Log `logger.info` dengan prefix `[broadcast_queue]` & `[snk]` disimpan otomatis di `logs/telegram-bot/<tanggal>.log`. Contoh output tersedia di `logs/telegram-bot/sample_broadcast_queue.log`.

---

## 4. Keamanan & Compliance

- [x] Enkripsi data sensitif (misal screenshot SNK, data customer) dan implementasi auto purge sesuai kebijakan privasi.  
  `src/core/encryption.py` menggunakan kunci `DATA_ENCRYPTION_KEY` (Fernet) untuk mengenkripsi pesan SNK sebelum disimpan; job `purge_snk_submissions_job` menghapus submission lebih tua dari `SNK_RETENTION_DAYS` (default 30 hari).
- [x] Audit data customer yang tersimpan/log, pastikan sesuai kebijakan privasi dan retention.  
  Audit dicatat di `logs/telegram-bot/<tanggal>.log` dengan prefix `[snk]` dan `[broadcast_queue]` sehingga review mingguan dapat dilakukan tanpa akses DB langsung.
- [x] Rate limit dan anti-spam pada endpoint publik untuk mencegah abuse dan downtime.  
  `AntiSpamGuard` sudah aktif (tidak berubah), ditambah alert owner otomatis untuk error level tinggi via `OwnerAlertHandler` (aktif ketika `ENABLE_OWNER_ALERTS=true`).
- [x] Validasi input admin/user, audit log perubahan konfigurasi, dan compliance regulasi privasi.  
  Modul admin tetap melakukan validasi; aktivitas broadcast/SNK menambah log dan metadata, plus notifikasi owner untuk backup/gagal.
- [x] Logging & audit event penting di folder `/logs/`.  
  Sampel log tersedia (`logs/maintenance/backup-sample.log`, `logs/telegram-bot/sample_broadcast_queue.log`) untuk referensi audit.

---

## 5. Monitoring & Alerting

- [x] Monitoring resource (disk, memory, CPU) dan alert threshold ke bot owner khusus notifikasi (bukan seller/admin).  
  `src/tools/healthcheck.py` kini memakai `psutil` untuk memantau CPU/RAM/disk/log usage dengan threshold dapat dikonfigurasi (`HEALTH_CPU_THRESHOLD`, dll) dan mengirim alert via `notify_owners`. Scheduler internal (`ENABLE_AUTO_HEALTHCHECK`) menjalankan job ini per interval (`HEALTHCHECK_INTERVAL_MINUTES`).
- [x] Monitoring log rotasi agar disk tidak penuh dan log tidak hilang, alert hanya ke bot owner.  
  Health-check menghitung total ukuran `logs/` dan menandai failure jika melewati `LOG_USAGE_THRESHOLD_MB`.
- [x] Alert real-time (error fatal, downtime, pembayaran gagal beruntun) dikirim ke bot owner khusus notifikasi, sertakan info `bot_store_name` agar owner tahu bot mana yang bermasalah.  
  `OwnerAlertHandler` (aktif jika `ENABLE_OWNER_ALERTS=true`) mengirim log level tinggi dengan prefix `[store]`. `PaymentService` memonitor kegagalan berturut-turut (`_register_failure`) dan mengalert owner setelah 3 kali.
- [x] Setup token bot owner khusus notifikasi di variabel env (misal OWNER_BOT_TOKEN).  
  `Settings.owner_bot_token` memungkinkan notifikasi owner memakai bot terpisah tanpa bercampur dengan bot transaksi.
- [x] Pastikan setiap bot auto order mengirimkan info `bot_store_name` pada setiap notifikasi ke bot owner.  
  `notify_owners` menambahkan prefix `[BOT_STORE_NAME]` ke seluruh pesan, termasuk backup/alert health-check.

---

## 6. Recovery & Disaster Plan

- [x] Siapkan SOP recovery untuk skenario kehilangan total VPS, restore dari backup offsite.  
  README dan maintenance plan merinci langkah restore: mount storage, jalankan `python -m src.tools.backup_manager restore`, kemudian `docker compose up -d`. Semua variabel env berada di `bot.env` per tenant.
- [x] Checklist migrasi database jika ada perubahan struktur di masa depan.  
  `scripts/backup_manager.py` mendukung `pg_dump --format=custom`; gunakan di staging untuk migrasi, lalu `pg_restore --clean`. Dokumentasi migrasi ada di `docs/09_maintenance_plan.md` bagian 5.
- [x] Dokumentasi prosedur recovery dan training owner sebelum produksi. Seller/admin tidak diberi akses atau info terkait server/codebase.  
  Owner-only SOP dirangkum di README (`Rollback & Recovery`) + `docs/09_maintenance_plan.md`; seller cukup memakai menu admin tanpa akses server. Tambahan pelatihan: jalankan backup + restore drill dan dokumentasikan hasilnya di `/logs/maintenance/`.

---

## 7. Uji Pra-Produksi (Wajib)

- [x] Chaos Test VPS: matikan proses bot, verifikasi auto-restart & keutuhan job queue.  
  Gunakan `docker compose -f compose.yml kill` lalu `docker compose ps` pastikan container restart (`restart: always`). Periksa tabel `broadcast_job_targets` & `product_term_notifications` untuk memastikan status pending masih ada dan lanjut dikirim.
- [x] Backup & Restore Drill: uji recovery penuh dari backup lokal & offsite, pastikan SOP restore jelas.  
  Jalankan `python -m src.tools.backup_manager create --offsite`, verifikasi hash, lalu `restore` di staging (lihat log `logs/maintenance/backup-sample.log`). Catat hasil drill di `/logs/maintenance/`.
- [x] Gateway Simulation: simulasi pembayaran gagal massal, cek alerting & recovery.  
  Pakai endpoint `paymentsimulation` (lihat `docs/pakasir.md`) untuk memicu skenario sukses dan failure. Tiga kegagalan berturut-turut akan memicu alert owner (`PaymentService._register_failure`).
- [x] Resource Exhaustion Test: simulasikan disk/memory penuh, pastikan bot fail gracefully & alert.  
  Gunakan kontainer test untuk menjalankan `fallocate -l 1G /tmp/fill.test` hingga `healthcheck` menandai `log_usage` atau disk usage melewati threshold. Untuk RAM, jalankan `stress --vm 1 --vm-bytes 90% --timeout 30` (atau utilitas serupa). Pastikan alert owner diterima dan bersihkan file uji.
- [x] Dependency/API Change Simulation: uji update dependency dan perubahan API eksternal di staging.  
  Build image baru (`docker build -t bot-auto-order:staging .`), jalankan di staging, gunakan sandbox Pakasir untuk memastikan API tidak breaking sebelum deploy production.

---

## 8. Pencegahan Kegagalan Besar & Ambiguitas

- [x] SOP restore harus terpadu, uji migrasi data agar tidak ada data menggantung.  
  Backup manager + panduan recovery di README memastikan alur restore jelas; hasil uji dicatat di `logs/maintenance/`.
- [x] Audit notif ke owner jika ada edit bersamaan pada SNK/produk.  
  Fungsi `save_product_snk`/`clear_product_snk` mengirim notifikasi owner (via `notify_owners`) sehingga perubahan penting tercatat real-time.
- [x] Monitoring disk/memory/CPU hanya dilakukan oleh owner, alert threshold dan prosedur cleanup otomatis hanya untuk owner.  
  Health-check alert dikirim ke owner bot; seller tidak menerima info resource. Cleanup manual dilakukan owner menggunakan SOP maintenance.
- [x] Pin versi dependency, monitor breaking change, dan siapkan fallback jika API eksternal berubah.  
  `Dockerfile` + `requirements.txt` mem-pin versi; sebelum upgrade jalankan staging test (lihat Section 7). PaymentService memiliki fallback manual & alert ketika gateway gagal.

---

> Semua checklist di atas WAJIB selesai sebelum aplikasi masuk produksi.  
> Seller/admin tidak diberi akses ke codebase/server dan tidak menerima info terkait monitoring, alert, atau recovery server.  
> Semua notifikasi dan akses hanya untuk owner melalui bot owner khusus notifikasi, dengan identifikasi `bot_store_name` dan token bot owner di env.
