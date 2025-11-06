# Project Context – Bot Auto Order Telegram

## Overview
Bot Auto Order Telegram adalah sistem otomatisasi pemesanan produk digital yang berjalan di platform Telegram, terintegrasi dengan payment gateway Pakasir (QRIS). Bot ini dirancang untuk memudahkan pembeli melakukan transaksi secara mandiri, sekaligus memberikan kontrol penuh kepada owner dan admin/seller untuk mengelola produk, order, dan konfigurasi bot langsung dari Telegram tanpa akses ke server atau codebase.

> **Update 6 Nov 2025:** Onboarding kini hanya mengirim satu pesan welcome + keyboard, informasi stok menggunakan timezone Asia/Jakarta, dan alur pembayaran/ deposit otomatis menambahkan biaya Pakasir (0,7% + Rp310) lengkap dengan pembersihan invoice kadaluarsa.

## Tujuan Utama
- Mempermudah proses pembelian produk digital via Telegram dengan alur yang cepat, jelas, dan ramah emoji.
- Menyediakan pembayaran otomatis dan aman melalui QRIS (Pakasir).
- Memberikan admin/seller tools untuk mengelola katalog, stok, harga, kupon, saldo, serta kustomisasi respon bot.
- Menjamin observability, audit, dan keamanan data melalui logging, backup, dan monitoring terpusat.
- Memastikan owner memiliki kontrol penuh atas monitoring, alert, dan recovery server melalui bot owner khusus notifikasi.

## Target User
- **Owner:** Pemilik toko digital, memiliki akses audit, monitoring, dan recovery server. Menerima notifikasi error, downtime, dan alert penting via bot owner khusus.
- **Admin/Seller:** Pengelola produk, order, user, dan konfigurasi bot melalui menu Telegram. Tidak memiliki akses ke server/codebase.
- **Pembeli:** User Telegram yang ingin membeli produk digital dengan proses mandiri, cepat, dan transparan.

## Platform
- **Telegram Bot:** Bot utama untuk interaksi pembeli dan admin/seller.
- **Bot Owner Khusus:** Bot terpisah untuk notifikasi monitoring, alert, dan recovery yang hanya diakses owner.
- **Backend:** Python 3.12+, modul utama di `src/`, database PostgreSQL/SQLite, integrasi API Pakasir.
- **Payment Gateway:** Pakasir (QRIS, webhook, sandbox).
- **Logging & Observability:** Folder `/logs/` untuk audit, monitoring, dan troubleshooting.
- **Backup & Restore:** Otomatis dan offsite, dengan SOP recovery dan alert ke owner.

## Konteks & Workflow
- Pembeli memulai interaksi dengan `/start`, memilih produk, menambah ke keranjang, dan melakukan pembayaran QRIS.
- Bot memproses pembayaran, mengirim SNK, dan menerima submission bukti SNK dari pembeli.
- Admin/seller mengelola produk, order, user, dan broadcast via menu Telegram.
- Owner menerima alert error, downtime, dan backup melalui bot owner khusus, serta mengelola recovery dan audit.
- Semua data, konfigurasi, dan log disimpan di database dan folder terpusat, dengan backup dan monitoring aktif.

## Terms and Conditions (Ringkasan)
- Proyek ini tunduk pada protokol anti-kecurangan, anti-penipuan, dan audit transparan.
- Seller/admin tidak diberi akses ke server/codebase dan tidak menerima info monitoring atau recovery.
- Semua notifikasi dan akses monitoring hanya untuk owner melalui bot owner khusus.
- Detail risiko, audit, dan penegakan aturan dapat dilihat di dokumen risk audit dan security policy.

---
