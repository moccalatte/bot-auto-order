bot-auto-order/docs/agents.md
# Agents – Bot Auto Order Telegram

## Overview
Dokumen ini menjelaskan peran dan workflow agents (AI & manusia) dalam pengembangan, audit, dan operasional bot auto order Telegram. Setiap agent memiliki tanggung jawab spesifik untuk menjaga kualitas, keamanan, dan efisiensi proyek.

---

## Types of Agents

### AI Agents
- **Builder Agent**
  - Implementasi fitur bot sesuai PRD dan arsitektur.
  - Integrasi Telegram API, payment gateway (Pakasir), admin tools, SNK handler, broadcast, dan logging.
  - Menulis kode modular, dokumentasi, dan contoh log/output.

- **Reviewer Agent**
  - Melakukan QA, analisis bug, dan refactor kode.
  - Memastikan compliance dengan dev_protocol dan security policy.
  - Memberikan feedback dan rekomendasi perbaikan.

- **Security Agent**
  - Audit keamanan: validasi input, enkripsi data sensitif, rate limit, dan anti-fraud.
  - Review log audit, mitigasi risiko, dan compliance regulasi privasi.

- **Doc Agent**
  - Menyusun dan memperbarui dokumentasi (README, PRD, arsitektur, changelog, maintenance).
  - Menyediakan contoh nyata (kode, log, output) untuk onboarding dan audit.

- **Integration Agent**
  - Mengelola koneksi API eksternal (Pakasir, Telegram).
  - Menangani webhook, error handling, dan fallback.

### Human Agents
- **Owner**
  - Memiliki akses penuh audit, monitoring, dan recovery server.
  - Menerima notifikasi error, downtime, dan alert penting via bot owner khusus notifikasi.
  - Mengambil keputusan final pada eskalasi masalah, migrasi, dan update roadmap.

- **Admin/Seller**
  - Mengelola produk, order, user, dan konfigurasi bot via menu Telegram.
  - Tidak memiliki akses ke codebase/server atau monitoring resource.
  - Menerima notifikasi order baru dan broadcast, tanpa akses audit server.

---

## Responsibilities

- Setiap agent menjalankan tugas sesuai protokol dan peran masing-masing.
- Semua perubahan penting, bug, dan audit harus terdokumentasi di log atau file terkait.
- AI agents wajib mematuhi dev_protocol, security policy, dan risk audit.
- Owner bertanggung jawab atas monitoring, backup, recovery, dan compliance.
- Admin/Seller hanya mengakses fitur bot yang diizinkan (menu Telegram).

---

## Communication & Workflow

- Komunikasi utama antar agent dilakukan melalui log file, notifikasi bot owner, dan dokumentasi.
- Builder Agent mengirim log build dan output ke folder `/logs/`.
- Reviewer Agent memberikan feedback QA di log atau file review.
- Security Agent melakukan audit berkala dan melaporkan temuan ke owner.
- Owner menerima alert error, downtime, dan backup via bot owner khusus notifikasi (dengan info bot_store_name).
- Admin/Seller menerima notifikasi order dan broadcast via bot auto order, tanpa akses monitoring server.

### Sample Workflow

1. Builder Agent push patch fitur baru → log build ke `/logs/`.
2. Reviewer Agent review patch → feedback QA di log.
3. Security Agent audit patch → log audit dan mitigasi.
4. Owner menerima alert error/downtime via bot owner → ambil keputusan recovery.
5. Admin/Seller kelola produk/order via menu Telegram → notifikasi order masuk.

#### Sample Log Komunikasi
```
[2025-11-12 10:15:00] [builder] Build success: SNK handler v1.2
[2025-11-12 10:15:01] [reviewer] QA feedback: SNK handler, 1 minor bug found
[2025-11-12 10:15:05] [builder] Patch applied: bug #101
[2025-11-12 10:15:10] [security] Audit: no fraud detected, compliance OK
[2025-11-12 10:16:00] [owner] ALERT: Bot 'store_xyz' downtime detected, recovery initiated
```

---

## Escalation & Recovery

- Jika AI agent gagal build/patch, Reviewer dan Security Agent melakukan rollback dan audit.
- Owner mengambil keputusan final pada masalah besar (data hilang, fraud, downtime).
- Semua recovery dan eskalasi harus terdokumentasi di log.

---

## Ethics & Compliance

- Semua agent wajib mematuhi protokol anti-kecurangan, anti-penipuan, dan audit.
- Dilarang manipulasi data, hasil, atau proses secara tidak sah.
- Setiap interaksi dan keputusan penting harus terdokumentasi.
- Owner bertanggung jawab atas compliance dan audit akhir.

---

## Catatan

Template ini dapat disesuaikan sesuai kebutuhan project dan jumlah/jenis agent yang terlibat.  
Pastikan seluruh workflow, komunikasi, dan audit berjalan transparan dan terdokumentasi.
