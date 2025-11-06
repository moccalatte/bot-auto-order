bot-auto-order/docs/06_risk_audit.md
# Risk & Audit – Bot Auto Order Telegram

Dokumen ini mengidentifikasi risiko utama, strategi mitigasi, dan protokol audit untuk proyek bot auto order Telegram yang terintegrasi dengan payment gateway Pakasir.

> **Update 6 Nov 2025:** Risiko baru: salah hitung biaya Pakasir & invoice menumpuk. Mitigasi: fungsi fee terpusat (`calculate_gateway_fee`), deposit service baru dengan verifikasi amount, dan job `check_expired_payments_job` kini membersihkan pesan user/admin secara idempotent.

---

## 1. Risk Identification

### Teknis
- **API Pakasir Down/Timeout**
  - Bot tidak bisa membuat invoice atau memproses pembayaran.
- **Database Corruption/Data Loss**
  - Hilangnya data produk, order, SNK, atau konfigurasi admin.
- **Backup Gagal**
  - Tidak ada backup valid saat terjadi insiden.
- **Stok Tidak Sinkron**
  - Stok produk tidak sesuai antara database dan realitas, menyebabkan oversell atau gagal order.
- **Webhook Gagal/Delay**
  - Status pembayaran tidak terupdate, order tertahan.
- **Resource Exhaustion (Disk/Memory/CPU)**
  - Bot crash, downtime, atau gagal proses transaksi.

### Operasional
- **Fraud/Abuse oleh User**
  - User mencoba manipulasi order, spam aksi, atau eksploitasi bug.
- **Admin Error**
  - Salah input, salah konfigurasi, atau restore data yang tidak valid.
- **Broadcast Abuse**
  - Admin mengirim broadcast berlebihan, menyebabkan spam ke user.

### Legal & Compliance
- **Data Privacy Breach**
  - Data pribadi user/admin bocor atau diakses tanpa izin.
- **Penyalahgunaan Bot untuk Penipuan**
  - Bot digunakan untuk transaksi ilegal atau scam.

---

## 2. Mitigation Plan

| Risiko                      | Mitigasi                                                                 |
|-----------------------------|--------------------------------------------------------------------------|
| API Pakasir Down            | Fallback pesan error, retry otomatis, opsi pembayaran manual.            |
| Database/Data Loss          | Backup otomatis & offsite, monitoring integritas backup, SOP restore.    |
| Backup Gagal                | Alert ke owner jika backup gagal/corrupt, uji restore berkala.           |
| Stok Tidak Sinkron          | Transaksi atomik, validasi stok sebelum checkout, audit log perubahan.   |
| Webhook Gagal/Delay         | Scheduler cek status order, retry webhook, log error detail.             |
| Resource Exhaustion         | Monitoring resource, alert threshold ke owner, prosedur cleanup otomatis.|
| Fraud/Abuse User            | Rate limit, anti-spam, audit log aksi user, notifikasi ke admin/owner.   |
| Admin Error                 | Validasi input, preview sebelum publish, audit log perubahan.            |
| Broadcast Abuse             | Limitasi frekuensi broadcast, audit log, notifikasi abuse ke owner.      |
| Data Privacy Breach         | Enkripsi data sensitif, role-based access, audit akses data.             |
| Penyalahgunaan Bot          | Audit transaksi, monitoring pola abuse, suspend/ban user/admin.          |

---

## 3. Audit Checklist

- [ ] Backup berjalan sesuai jadwal dan valid (uji restore minimal mingguan).
- [ ] Semua transaksi tercatat di log (success, failed, expired).
- [ ] Perubahan konfigurasi admin tercatat di audit log.
- [ ] Stok produk diverifikasi setiap hari.
- [ ] Webhook status order diverifikasi dan log error dicek.
- [ ] Resource (disk, memory, CPU) dimonitor dan alert threshold aktif.
- [ ] Rate limit dan anti-spam aktif, log abuse dicek.
- [ ] Data sensitif terenkripsi dan akses dibatasi.
- [ ] Broadcast dicek agar tidak melebihi batas wajar.
- [ ] Semua pelanggaran, fraud, atau abuse didokumentasikan di log dan ditindaklanjuti.

---

## 4. Reporting & Enforcement

- Semua temuan audit, error, fraud, atau abuse wajib dilaporkan ke owner melalui bot owner khusus notifikasi.
- Audit log disimpan di `/logs/audit/YYYY-MM-DD.log` dan direview minimal mingguan.
- Jika ditemukan fraud, abuse, atau pelanggaran privasi:
  - Lakukan suspend/ban user/admin terkait.
  - Rollback patch/konfigurasi bermasalah.
  - Dokumentasikan tindakan di audit log dan release notes.
- Proses audit dan penegakan aturan harus transparan dan terdokumentasi.

---

## 5. Terms and Conditions

### Anti-Fraud & Anti-Cheating
- Dilarang melakukan manipulasi data, hasil, atau proses secara tidak sah.
- Semua tindakan kecurangan akan didokumentasikan dan ditindak sesuai protokol audit.

### Anti-Scam & False Accusation
- Dilarang melakukan penipuan atau memberikan informasi palsu.
- Penuduhan tanpa bukti akan dicatat dan diverifikasi sebelum tindakan diambil.

### Enforcement
- Pelanggaran terhadap ketentuan ini dapat berakibat pada pembatasan akses, rollback, atau audit khusus.
- Semua proses audit dan penanganan pelanggaran harus transparan dan terdokumentasi di folder `/logs/`.

---

## 6. Sample Audit Log

```
[2025-11-12 10:23:45] [ERROR] Fraud detected: Unvalidated payment patch by AI agent.
[2025-11-12 10:23:46] [ACTION] Rollback patch to commit a1b2c3d.
[2025-11-12 10:23:47] [INFO] AI agent instructed to add input validation and retest.
[2025-11-12 11:00:00] [ENFORCEMENT] Access to payment module restricted for admin_id=123456 due to repeated fraud attempts.
[2025-11-12 11:01:00] [ROLLBACK] All changes after commit a1b2c3d reverted.
[2025-11-12 11:02:00] [AUDIT] Special audit scheduled for payment module.
[2025-11-15 02:00:00] [INFO] Backup database selesai: backup/db_2025-11-15.sql
[2025-11-15 02:10:00] [WARN] Patch keamanan diterapkan pada modul auth
[2025-11-15 02:15:00] [INFO] Monitoring: CPU usage normal, RAM usage 60%
```

---

## 7. Compliance

- Pastikan project mematuhi regulasi privasi dan keamanan data (misal: GDPR, aturan lokal).
- Jangan simpan data personal/sensitif tanpa persetujuan dan mekanisme proteksi.
- Audit eksternal direkomendasikan untuk project yang berkembang ke skala besar/enterprise.
- Semua aktivitas audit dan maintenance harus mematuhi protokol anti-kecurangan dan anti-penipuan.

---

> Dokumen ini wajib direview dan diupdate setiap kali ada perubahan besar pada arsitektur, fitur, atau protokol keamanan.
