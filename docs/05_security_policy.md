bot-auto-order/docs/05_security_policy.md
# Security Policy – Bot Auto Order Telegram

Dokumen ini merangkum kebijakan keamanan, autentikasi, validasi, logging, dan mitigasi risiko untuk bot auto order Telegram yang terintegrasi dengan Pakasir.

---

## 1. Authentication & Authorization

- **Admin/Seller Authentication:**  
  Hanya admin/seller yang terdaftar di database (berdasarkan Telegram ID) dapat mengakses menu admin bot. Owner memiliki hak audit penuh dan override.
- **Owner Notification:**  
  Semua notifikasi terkait error, monitoring, dan recovery hanya dikirim ke bot owner khusus notifikasi, bukan ke seller/admin.
- **No Codebase/Server Access for Seller:**  
  Seller/admin tidak diberi akses ke server, codebase, atau resource monitoring.

---

## 2. Input Validation

- **Sanitasi Input:**  
  Semua input dari user/admin divalidasi dan disanitasi sebelum diproses atau disimpan ke database.
- **Template Validation:**  
  Validasi placeholder pada template pesan admin (misal: `{nama}`, `{order_id}`) sebelum publish.
- **Webhook Validation:**  
  Payload webhook dari Pakasir divalidasi signature jika tersedia (`PAKASIR_WEBHOOK_SECRET`).

---

## 3. Encryption & Secrets

- **Environment Variables:**  
  Semua kredensial (API key, webhook secret, bot token) disimpan di file `.env` dan masuk `.gitignore`.
- **Sensitive Data:**  
  Data sensitif (screenshot SNK, data customer) dienkripsi di database menggunakan kunci `DATA_ENCRYPTION_KEY` (Fernet) dan hanya dapat diakses oleh admin/owner yang berwenang. Retensi diatur lewat `SNK_RETENTION_DAYS`.
- **No Hardcoded Secrets:**  
  Dilarang menyimpan credential atau data sensitif di source code.

---

## 4. Rate Limiting & Anti-Spam

- **User Rate Limit:**  
  User tidak boleh mengirim aksi lebih cepat dari 1 detik secara terus menerus. Jika melampaui ambang batas, bot balas peringatan dan laporkan ke admin.
- **Admin Rate Limit:**  
  Admin juga dibatasi untuk aksi broadcast dan perubahan konfigurasi agar tidak overload sistem.
- **API Throttling:**  
  Semua request ke Pakasir dan endpoint eksternal menggunakan retry/backoff dan rate limit.

---

## 5. Logging & Audit

- **Log Format:**  
  Semua log menggunakan format `[timestamp] [level] message` dan disimpan di folder `/logs/telegram-bot/{date}.log`.
- **Audit Log:**  
  Setiap perubahan konfigurasi, aksi admin, dan event penting dicatat di audit log untuk keperluan review dan rollback.
- **Retention Policy:**  
  Log disimpan minimal 30 hari, rotasi otomatis, dan monitoring disk usage aktif.

---

## 6. Anti-Fraud & Anti-Scam

- **Fraud Detection:**  
  Semua transaksi dan perubahan data penting diaudit. Jika terdeteksi fraud (misal: manipulasi order, bypass pembayaran), lakukan rollback dan laporkan ke owner.
- **False Accusation:**  
  Penuduhan fraud/penipuan tanpa bukti log akan diverifikasi sebelum tindakan diambil.
- **Enforcement:**  
  Pelanggaran berat dapat berakibat pembatasan akses, rollback, atau audit khusus.

---

## 7. Compliance & Privacy

- **Data Privacy:**  
  Data pribadi buyer/seller dijaga privasinya, hanya admin/owner yang berwenang dapat mengakses.
- **Regulasi:**  
  Project mematuhi regulasi privasi dan keamanan data (misal: GDPR, aturan lokal).
- **Consent:**  
  Tidak menyimpan data personal/sensitif tanpa persetujuan dan mekanisme proteksi.

---

## 8. External Audit & Tools

- **Static/Dynamic Analysis:**  
  Rekomendasikan audit eksternal dengan tools seperti Bandit (Python), SAST/DAST, dan dependency checker.
- **Audit Log Documentation:**  
  Semua hasil audit eksternal didokumentasikan di folder `/logs/` dan release notes.

---

## 9. Emergency & Recovery

- **Incident Response:**  
  Jika terjadi insiden keamanan (data leak, fraud, downtime), lakukan recovery sesuai SOP di maintenance plan dan dokumentasikan di log.
- **Owner Escalation:**  
  Semua insiden dan recovery wajib diinformasikan ke owner melalui bot owner khusus notifikasi.

---

## 10. Sample Security Snippet

```python
# Input validation example
def sanitize_input(user_input: str) -> str:
    return user_input.replace(";", "").replace("--", "")

# Logging example
def log_event(level, message):
    from datetime import datetime
    with open(f"logs/telegram-bot/{datetime.now():%Y-%m-%d}.log", "a") as f:
        f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [{level}] {message}\n")
```

---

## 11. Checklist Security Implementation

- [x] Autentikasi admin/seller via Telegram ID
- [x] Validasi input & template pesan
- [x] Enkripsi data sensitif & simpan credential di .env
- [x] Rate limit user & admin
- [x] Logging & audit event penting
- [x] Audit fraud & penipuan
- [x] Compliance privasi & regulasi
- [x] Monitoring log & disk usage
- [x] SOP recovery insiden

---

> Semua kebijakan di atas wajib diterapkan sebelum bot auto order Telegram masuk produksi. Update dokumen ini jika ada perubahan arsitektur, fitur, atau regulasi baru.
