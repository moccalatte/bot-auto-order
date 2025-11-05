# 📋 Critical Steps for Production Readiness Bot Auto Order

Dokumen ini hanya berisi langkah-langkah fatal/critical yang wajib diimplementasikan sebelum aplikasi masuk produksi. Fokus pada pencegahan kegagalan besar, kehilangan data, downtime, dan risiko bisnis utama.

---

## 1. Infrastruktur & Ketahanan Server

- [ ] Implementasi failover: siapkan mode polling + webhook, serta dokumentasi prosedur switch DNS/Reverse Proxy.
- [ ] Buat skrip health-check otomatis untuk mendeteksi downtime dan alert ke admin.
- [ ] Tambahkan supervisor/systemd unit dengan restart policy agar bot auto-restart jika crash.
- [ ] Uji chaos: matikan proses bot secara paksa, pastikan auto-restart dan job queue tetap utuh.

---

## 2. Backup & Restore

- [ ] Implementasi backup otomatis dan terenkripsi untuk database, .env, konfigurasi, dan log.
- [ ] Backup offsite (cloud/remote server) untuk mitigasi kehilangan total VPS.
- [ ] Monitoring integritas backup: alert jika backup gagal atau corrupt.
- [ ] Uji restore berkala dari backup lokal dan offsite, pastikan data konsisten dan SOP mudah diikuti.
- [ ] Terapkan versioning & retention policy agar backup tidak menumpuk dan mudah diakses saat recovery.

---

## 3. Job Queue & Data Integrity

- [ ] Pastikan job queue (SNK pending, broadcast) persisten dan tidak hilang saat restart/crash.
- [ ] Implementasi distributed lock pada job critical jika ada multi-instance/standby VPS.
- [ ] Validasi idempotensi pada penjadwalan job agar tidak terjadi duplikasi atau kehilangan notifikasi.

---

## 4. Keamanan & Compliance

- [ ] Rotasi kredensial API & token Telegram secara berkala, serta reminder otomatis ke admin.
- [ ] Enkripsi data sensitif (misal screenshot SNK) dan implementasi auto purge sesuai kebijakan privasi.
- [ ] Audit data customer yang tersimpan/log, pastikan sesuai kebijakan privasi dan retention.
- [ ] Rate limit dan anti-spam pada endpoint publik untuk mencegah abuse dan downtime.

---

## 5. Monitoring & Alerting

- [ ] Implementasi monitoring resource (disk, memory, CPU) dan alert threshold ke owner (bukan seller/admin).
- [ ] Monitoring log rotasi agar disk tidak penuh dan log tidak hilang, alert hanya ke owner.
- [ ] Alert real-time jika terjadi error fatal, downtime, atau pembayaran gagal beruntun, hanya ke owner.

---

## 6. Recovery & Disaster Plan

- [ ] Siapkan SOP recovery untuk skenario kehilangan total VPS, restore dari backup offsite.
- [ ] Checklist migrasi database jika ada perubahan struktur di masa depan.
- [ ] Dokumentasi prosedur recovery dan training owner sebelum produksi. Seller/admin tidak diberi akses atau info terkait server/codebase.

---

> Checklist di atas WAJIB selesai sebelum aplikasi masuk produksi. Item opsional/non-critical dapat ditambahkan setelah aplikasi stabil.