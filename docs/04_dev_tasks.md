bot-auto-order/docs/04_dev_tasks.md
# Development Tasks – Bot Auto Order Telegram

Roadmap dan milestone development untuk proyek bot auto order Telegram, terintegrasi dengan Pakasir dan admin tools berbasis Telegram.

> **Update 6 Nov 2025:** Task baru: (a) normalisasi fee Pakasir di invoice & deposit, (b) implementasi deposit QRIS penuh + cleanup scheduler, (c) UX refinement welcome tunggal & perlindungan checkout kosong. Milestone terkait ditandai selesai pada rilis 0.5.4.

---

## Milestone 1 – Setup & Inisialisasi
- [x] Inisialisasi repo & struktur folder (`src/`, `logs/`, `tests/`, `docs/`)
- [x] Setup environment: virtualenv, `.env`, `requirements.txt`
- [x] Dokumentasi awal: `README.md`, starterkit di `docs/`

## Milestone 2 – Fitur Dasar Bot
- [x] Implementasi command `/start` (onboarding, statistik, emoji, keyboard)
- [x] Navigasi produk: kategori, daftar produk, detail produk, keranjang belanja
- [x] CRUD produk & kategori via admin menu Telegram
- [x] Validasi stok & harga sebelum checkout

## Milestone 3 – Integrasi Pembayaran & SNK
- [x] Integrasi API Pakasir: invoice QRIS, webhook pembayaran, status order
- [x] Penanganan invoice kadaluarsa, error, dan fallback manual
- [x] Fitur SNK per produk: pengiriman otomatis SNK, tombol `✅ Penuhi SNK`, audit submission customer

## Milestone 4 – Admin Tools & Customization
- [x] Menu admin Telegram: kelola produk, order, user, template pesan event
- [x] Fitur broadcast pesan (teks/foto) ke seluruh user aktif
- [x] Backup & restore konfigurasi bot (template, produk, dsb)
- [x] Audit log perubahan konfigurasi dan aktivitas admin

## Milestone 5 – Observability & Monitoring
- [x] Logging interaksi, error, dan perubahan konfigurasi ke folder `/logs/`
- [x] Monitoring metrik ringan: transaksi, error rate, user aktif
- [x] Health-check & alert downtime ke bot owner khusus notifikasi (dengan info `bot_store_name`)
- [x] Early warning pembayaran gagal beruntun ke bot owner

## Milestone 6 – Keamanan & Anti-Fraud
- [x] Validasi input admin & user, anti-spam, rate limit
- [x] Enkripsi data sensitif (kredensial, screenshot SNK, dsb)
- [x] Audit log anti-fraud, rollback patch jika ditemukan pelanggaran

## Milestone 7 – QA, Testing & Deployment
- [x] Unit test & integration test (mock API Pakasir, validasi logic utama)
- [x] Refactor modularisasi kode sesuai dev_protocol
- [x] Deploy ke staging VPS, uji backup & restore, simulasi resource exhaustion
- [x] Final QA: review bug, compliance, dan observability

## Milestone 8 – Release & Maintenance
- [x] Update changelog dan release notes di `docs/08_release_notes.md`
- [x] Setup backup otomatis & monitoring di production
- [x] Dokumentasi maintenance plan, emergency SOP, dan migrasi
- [x] Training owner/admin untuk operasional bot

---

## Checklist Verifikasi & Log
- [x] Setiap milestone diverifikasi dengan contoh input/output nyata
- [x] Semua perubahan dan hasil milestone terdokumentasi di folder `/logs/`
- [x] Jika ada rollback, catat langkah dan alasan di log
- [x] Semua patch dan update tercatat di release notes

---

## Contoh Log Milestone

```
[2025-11-21 10:00:00] [INFO] Milestone 2: Fitur onboarding dan navigasi produk selesai.
[2025-11-21 10:05:00] [INFO] Milestone 3: Integrasi API Pakasir sukses, webhook pembayaran aktif.
[2025-11-21 10:10:00] [WARN] Milestone 5: Error rate meningkat, alert dikirim ke bot owner.
[2025-11-21 10:15:00] [ROLLBACK] Patch anti-spam dinonaktifkan sementara, bug ditemukan.
```

---

## Next Steps

- Review milestone yang belum selesai dan update roadmap di PRD.
- Lakukan audit QA dan security sebelum go-live.
- Update dokumentasi jika ada perubahan besar pada workflow atau arsitektur.

---
