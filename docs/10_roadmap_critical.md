# 🚨 Roadmap & Critical Steps – Bot Auto Order Telegram

Dokumen ini menggabungkan roadmap dan langkah-langkah fatal/critical yang wajib diterapkan sebelum bot auto order Telegram masuk produksi. Fokus pada pencegahan kegagalan besar, kehilangan data, downtime, keamanan, dan compliance. Semua item di bawah WAJIB selesai sebelum go-live. Fitur opsional/non-critical dapat ditambahkan setelah aplikasi stabil.

---

## 1. Infrastruktur & Ketahanan Server

- [ ] Implementasi failover: mode polling + webhook, dokumentasi prosedur switch DNS/Reverse Proxy.
- [ ] Skrip health-check otomatis untuk mendeteksi downtime dan alert ke bot owner khusus notifikasi.
- [ ] Supervisor/systemd unit dengan restart policy agar bot auto-restart jika crash.
- [ ] Uji chaos: matikan proses bot secara paksa, pastikan auto-restart dan job queue tetap utuh.
- [ ] Distributed lock untuk job queue pada multi-instance/standby VPS.

---

## 2. Backup & Restore

- [ ] Backup otomatis dan terenkripsi untuk database, .env, konfigurasi, dan log.
- [ ] Backup offsite (cloud/remote server) untuk mitigasi kehilangan total VPS.
- [ ] Monitoring integritas backup: alert ke bot owner jika backup gagal/corrupt.
- [ ] Uji restore berkala dari backup lokal dan offsite, pastikan data konsisten dan SOP mudah diikuti.
- [ ] Terapkan versioning & retention policy agar backup tidak menumpuk dan mudah diakses saat recovery.

---

## 3. Job Queue & Data Integrity

- [ ] Pastikan job queue (SNK pending, broadcast) persisten dan tidak hilang saat restart/crash.
- [ ] Validasi idempotensi pada penjadwalan job agar tidak terjadi duplikasi atau kehilangan notifikasi.
- [ ] Audit log untuk setiap perubahan dan eksekusi job critical.

---

## 4. Keamanan & Compliance

- [ ] Enkripsi data sensitif (misal screenshot SNK, data customer) dan implementasi auto purge sesuai kebijakan privasi.
- [ ] Audit data customer yang tersimpan/log, pastikan sesuai kebijakan privasi dan retention.
- [ ] Rate limit dan anti-spam pada endpoint publik untuk mencegah abuse dan downtime.
- [ ] Validasi input admin/user, audit log perubahan konfigurasi, dan compliance regulasi privasi.
- [ ] Logging & audit event penting di folder `/logs/`.

---

## 5. Monitoring & Alerting

- [ ] Monitoring resource (disk, memory, CPU) dan alert threshold ke bot owner khusus notifikasi (bukan seller/admin).
- [ ] Monitoring log rotasi agar disk tidak penuh dan log tidak hilang, alert hanya ke bot owner.
- [ ] Alert real-time (error fatal, downtime, pembayaran gagal beruntun) dikirim ke bot owner khusus notifikasi, sertakan info `bot_store_name` agar owner tahu bot mana yang bermasalah.
- [ ] Setup token bot owner khusus notifikasi di variabel env (misal OWNER_BOT_TOKEN).
- [ ] Pastikan setiap bot auto order mengirimkan info `bot_store_name` pada setiap notifikasi ke bot owner.

---

## 6. Recovery & Disaster Plan

- [ ] Siapkan SOP recovery untuk skenario kehilangan total VPS, restore dari backup offsite.
- [ ] Checklist migrasi database jika ada perubahan struktur di masa depan.
- [ ] Dokumentasi prosedur recovery dan training owner sebelum produksi. Seller/admin tidak diberi akses atau info terkait server/codebase.

---

## 7. Uji Pra-Produksi (Wajib)

- [ ] Chaos Test VPS: matikan proses bot, verifikasi auto-restart & keutuhan job queue.
- [ ] Backup & Restore Drill: uji recovery penuh dari backup lokal & offsite, pastikan SOP restore jelas.
- [ ] Gateway Simulation: simulasi pembayaran gagal massal, cek alerting & recovery.
- [ ] Resource Exhaustion Test: simulasikan disk/memory penuh, pastikan bot fail gracefully & alert.
- [ ] Dependency/API Change Simulation: uji update dependency dan perubahan API eksternal di staging.

---

## 8. Pencegahan Kegagalan Besar & Ambiguitas

- [ ] SOP restore harus terpadu, uji migrasi data agar tidak ada data menggantung.
- [ ] Audit notif ke owner jika ada edit bersamaan pada SNK/produk.
- [ ] Monitoring disk/memory/CPU hanya dilakukan oleh owner, alert threshold dan prosedur cleanup otomatis hanya untuk owner.
- [ ] Pin versi dependency, monitor breaking change, dan siapkan fallback jika API eksternal berubah.

---

> Semua checklist di atas WAJIB selesai sebelum aplikasi masuk produksi.  
> Seller/admin tidak diberi akses ke codebase/server dan tidak menerima info terkait monitoring, alert, atau recovery server.  
> Semua notifikasi dan akses hanya untuk owner melalui bot owner khusus notifikasi, dengan identifikasi `bot_store_name` dan token bot owner di env.
