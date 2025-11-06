bot-auto-order/docs/09_maintenance_plan.md
# Maintenance Plan – Bot Auto Order Telegram

Dokumen ini memuat panduan lengkap perawatan, backup, monitoring, dan update untuk menjaga stabilitas dan keamanan bot auto order Telegram.

> **Update 6 Nov 2025:** Pastikan job `check_expired_payments_job` tetap aktif karena kini mengurus cleaning invoice & deposit. Monitoring log wajib memeriksa entri `[expired_payments]` dan `[expired_deposits]` untuk memastikan tidak ada pesan tersisa di chat.

---

## 1. Backup

### Jadwal & Lokasi
- **Default lokal**: `BACKUP_LOCAL_DIR` (default `backups/local/`).
- **Offsite**: mount storage eksternal (SFTP/NFS/rclone) ke `BACKUP_OFFSITE_DIR` (default `backups/offsite/`).
- **Frekuensi**: jalankan `python -m src.tools.backup_manager create --offsite` harian (via cron/docker scheduler).

### Prosedur Backup Manual
```bash
export BACKUP_ENCRYPTION_PASSWORD='rahasia-super'
python -m src.tools.backup_manager create --offsite
```
- `backup_manager` otomatis membuat dump database (format custom), menyalin `.env` & konfigurasi penting, serta mengarsipkan log.
- Arsip terenkripsi: `backups/local/backup-YYYYMMDD-HHMMSS.tar.gz.enc`
- Metadata hash: `*.enc.meta.json`
- Data SNK pada tabel `product_term_submissions` tersimpan terenkripsi (AES-256/Fernet). Pastikan `DATA_ENCRYPTION_KEY` dicadangkan secara aman.

- **Monitoring Backup**
  - Backup otomatis berjalan di dalam container bila `ENABLE_AUTO_BACKUP=true`. Jadwal diatur via `BACKUP_TIME` (format `HH:MM`, timezone mengikuti `BOT_TIMEZONE`). `BACKUP_AUTOMATIC_OFFSITE` menentukan apakah direktori offsite ikut terisi.
  - Skrip mengirim alert ke owner menggunakan `notify_owners` ketika backup sukses/gagal.
  - Verifikasi integritas dengan `python -m src.tools.backup_manager verify <file>`.
  - Uji restore bulanan: jalankan `python -m src.tools.backup_manager restore <file>` di environment staging dan catat hasilnya di `/logs/maintenance/`.
  - Gunakan `python -m src.tools.backup_manager prune --keep <N>` untuk menerapkan kebijakan retensi.
  - Jika ingin kendali di host (mis. sinkronisasi object storage), kombinasikan dengan `scripts/cron_backup.sh`.
  - Job harian `purge_snk_submissions_job` otomatis menghapus submission SNK lebih lama dari `SNK_RETENTION_DAYS` (default 30 hari); pantau log `[snk] Purge ...`.

---

## 2. Monitoring

### Observability
- Logging aktif di semua mode (dev, test, production).
- Format log: `[timestamp] [level] message` disimpan di `/logs/bot-order/YYYY-MM-DD.log`.
- Metrik ringan: jumlah transaksi, error rate, uptime, resource usage (CPU, RAM, disk).

### Log Retention
- Log disimpan minimal 90 hari, lalu diarsipkan/offsite.
- Rotasi log otomatis setiap hari.
- Monitoring disk usage dan alert jika disk hampir penuh.

### Health Check
- Health-check berjalan otomatis di dalam container jika `ENABLE_AUTO_HEALTHCHECK=true` (interval `HEALTHCHECK_INTERVAL_MINUTES`). Jika ingin redundansi dari host, jalankan `python -m src.tools.healthcheck` via cron/systemd timer atau gunakan `scripts/cron_healthcheck.sh`.
- Alert real-time ke bot owner khusus notifikasi jika bot down, resource kritis, atau error fatal.
- Sertakan info `bot_store_name` pada setiap alert agar owner tahu bot mana yang bermasalah.

---

## 3. Update & Patch

### Update Library & Dependency
- Audit dependency setiap bulan, update ke versi stabil dan aman.
- Catat perubahan dependency di `docs/08_release_notes.md`.
- Lakukan testing di staging sebelum update di production.
- Untuk lingkungan Docker: build ulang image (`docker build -t bot-auto-order:latest .`), lalu rolling restart tiap tenant (`docker compose -f compose.yml pull && docker compose -f compose.yml up -d`).

### Patch & Bugfix
- Semua patch dan bugfix didokumentasikan di log dan release notes.
- Jika patch gagal, lakukan rollback dan catat langkah di `/logs/maintenance/`.

---

## 4. Emergency & Recovery

### Prosedur Emergency
- Jika bot gagal total, lakukan restore dari backup terbaru.
- Ikuti SOP recovery: restore database, konfigurasi, dan log.
- Dokumentasikan setiap langkah recovery di `/logs/maintenance/`.

### Checklist Recovery
- [ ] Database sudah direstore
- [ ] Konfigurasi sudah dipulihkan
- [ ] Log sudah tersedia
- [ ] Bot sudah running & terhubung ke Telegram
- [ ] Health-check sudah normal
- [ ] Owner sudah menerima notifikasi recovery

---

## 5. Migration Guideline

### Migrasi ke Production/Server Baru
1. Export data dari database lama ke format CSV/SQL.
2. Import data ke database production.
3. Update environment variable di `.env.production`.
4. Jalankan test integrasi dan verifikasi hasil migrasi di log.
5. Pastikan backup & monitoring aktif sebelum go-live.

---

## 6. Audit & Compliance

- Semua aktivitas maintenance harus terdokumentasi di log.
- Proses maintenance wajib mematuhi protokol audit dan anti-kecurangan (`docs/06_risk_audit.md`).
- Jika ada perubahan signifikan, lakukan review dan update dokumen terkait.

---

## 7. Maintenance Log (Sample)

```
[2025-11-15 02:00:00] [INFO] Backup database selesai: backup/db/db_2025-11-15.sql
[2025-11-15 02:05:00] [INFO] Update dependency: python-telegram-bot==20.3
[2025-11-15 02:10:00] [WARN] Patch keamanan diterapkan pada modul payment
[2025-11-15 02:15:00] [INFO] Monitoring: CPU usage normal, RAM usage 60%
[2025-11-15 02:20:00] [ERROR] Health-check: bot down, alert sent to owner bot
```

---

## 8. Checklist Maintenance

- [ ] Backup database & konfigurasi berjalan otomatis
- [ ] Backup offsite aktif & terverifikasi
- [ ] Monitoring & alert ke owner bot berjalan
- [ ] Log rotasi & retention sesuai kebijakan
- [ ] Update dependency & patch terdokumentasi
- [ ] SOP recovery tersedia & diuji
- [ ] Audit maintenance tercatat di log
- [ ] Status container dicek rutin (`docker compose ps` per tenant)

---

> Pastikan semua proses maintenance dilakukan rutin, terdokumentasi, dan sesuai protokol keamanan serta audit. Jika terjadi insiden, recovery harus cepat dan transparan ke owner.
