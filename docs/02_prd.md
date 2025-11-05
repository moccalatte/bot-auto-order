# Product Requirements Document – Bot Auto Order Telegram

## Referensi
- `docs/00_context.md` – gambaran alur interaksi pengguna dan admin.
- `docs/pakasir.md` – panduan integrasi payment gateway Pakasir.
- `docs/01_dev_protocol.md` – aturan struktur proyek, observability, dan praktik kolaborasi.

## Ringkasan
Bot Telegram auto-order untuk toko digital dengan pembayaran terhubung Pakasir. Menggunakan bahasa Indonesia baku bernuansa santai; setiap respons bot wajib kaya emoji agar terasa hidup. Admin dapat mengelola produk, kategori, pesan balasan kustom, dan konfigurasi utama bot langsung dari menu Telegram tanpa akses ke codebase.

## Tujuan
- Mempermudah pembeli memesan produk digital via Telegram secara mandiri.
- Menyediakan jalur pembayaran otomatis melalui Pakasir (khususnya QRIS).
- Menjamin admin dapat memantau stok, transaksi, dan saldo pengguna dari satu antarmuka bot.

## Target Pengguna
- **Pembeli**: pengguna Telegram yang ingin membeli produk digital dengan proses cepat dan jelas.
- **Admin**: pemilik toko yang mengatur katalog, stok, harga, kupon, saldo pengguna, serta kustomisasi respon bot dan pengaturan utama melalui menu admin Telegram.

## Ruang Lingkup Fitur
1. **Onboarding `/start`**
   - Pesan sambutan bergaya emoji dan menyertakan statistik total user & transaksi.
   - Inline keyboard kategori (termasuk 🧭 Semua Produk) dan ReplyKeyboard utama (📋 List Produk, 📦 Semua Produk, 📊 Cek Stok, 1️⃣, 2️⃣, 3️⃣, dst).
2. **Navigasi Produk**
   - Inline keyboard menampilkan kategori serta daftar produk menurut `early_plan.md`.
   - Format setiap produk memuat nama, harga, stok, total penjualan, emoji tematik (mis. 🔥, 🎟️, 💾).
3. **Detail Produk & Cart**
   - Pesan detail produk memuat harga, stok, kategori dengan emoji (contoh: 🛒, 💲, 📦).
   - Inline keyboard tindakan (➖, ➕, 🧺 Lanjut ke Keranjang, ❌ Batal) dan opsi kuantitas (✌️ x2, 🖐️ x5, 🔟 x10).
4. **Keranjang Belanja**
   - Ringkasan item dengan pembuka emoji (⛺, 🧾) dan peringatan pembayaran (🚫).
   - Inline keyboard (🎟️ Gunakan Kupon, 💳 Lanjut ke Pembayaran, ❌ Batal).
5. **Pembayaran via Pakasir**
   - Langkah memilih metode (🧊 Silakan Pilih Metode Pembayaran) dengan tombol 💠 QRIS, 💼 Saldo, ❌ Batalkan.
   - Integrasi API Pakasir `transactioncreate` (metode `qris`) atau URL `https://pots.my.id/pay/{slug}/{amount}?order_id={order_id}&qris_only=1`.
   - Penanganan loading (🎲 Sedang memuat...) dan invoice sukses (🏷️ Invoice Berhasil Dibuat).
   - Pengelolaan kadaluarsa: hapus pesan invoice, kirim stiker, dan notifikasi 📝 Tagihan Kadaluarsa.
6. **Saldo & Deposit**
   - Reply keyboard 💼 Deposit untuk opsi manual (admin input) atau otomatis via Pakasir.
   - Riwayat saldo ditampilkan dengan emoji status (✅, ⏳, ❌).
7. **Kupon & Diskon**
   - Opsi 🎟️ Gunakan Kupon sebelum pembayaran, validasi langsung di bot.
8. **Admin Tools & Customization**
   - Menu admin Telegram untuk kelola respon bot (template pesan event), produk (CRUD & upload gambar), order (lihat & update status), dan user (blokir/unblokir, lihat riwayat).
   - Fitur preview sebelum publish, validasi placeholder (misal: {nama}, {order_id}), backup & restore konfigurasi, serta audit log setiap perubahan.
   - Semua perubahan konfigurasi disimpan di database, bukan hardcode.
   - Dashboard ringkas via command admin (`/admin`, ⚙️ Pengaturan).
9. **SNK Produk & Monitoring**
   - Admin dapat menambahkan Syarat & Ketentuan (SNK) khusus per produk.
   - Bot mengirim SNK otomatis setelah pembayaran sukses dan menyediakan tombol `✅ Penuhi SNK` bagi customer untuk mengirim bukti (teks/foto) yang diteruskan ke admin.
10. **Broadcast Pesan Admin**
    - Admin dapat mengirim pesan custom (teks atau foto) ke semua user yang pernah `/start`, mengabaikan user yang memblokir bot atau diblokir admin.
11. **Notifikasi Pesanan ke Seller**
    - Setiap order baru menerbitkan notifikasi otomatis ke daftar admin (tanpa owner) berisi ringkasan pesanan, metode pembayaran, dan timestamp lokal.

## Alur Pengguna (Ringkas)
1. `User` kirim `/start` → Bot kirim sambutan emoji + statistik + inline kategori dan reply keyboard utama.
2. `User` pilih kategori atau `🧭 Semua Produk` → Bot kirim daftar produk dengan format bernomor + emoji.
3. `User` pilih produk (via nomor di reply keyboard atau inline) → Bot kirim detail + tombol `➕`.
4. `User` tambahkan produk (kondisi stok dicek) → Bot update pesan dengan jumlah di keranjang.
5. `User` klik `🧺 Lanjut ke Keranjang` → Bot tampilkan ringkasan, opsi kupon, lanjut bayar.
6. `User` pilih `💳 Lanjut ke Pembayaran` → Bot kirim pilihan metode (default `💠 QRIS`).
7. `User` pilih QRIS → Bot panggil API Pakasir, tampilkan QR & link mini app `🔗 Checkout URL`.
   - Jika sukses: tampilkan pesan sukses plus detail produk & S&K (emoji `🎉`, `📦`).
   - Jika kadaluarsa: hapus invoice, kirim stiker + pesan `📜 Tagihan Kadaluarsa`.
8. Setelah status order `paid/completed` → Bot mengirim pesan SNK (per produk) ke customer beserta tombol `✅ Penuhi SNK`. Customer yang menekan tombol dapat mengirim bukti dan keterangan; bot mencatat dan meneruskan informasi ke seller/admin (owner dikecualikan).

## Persyaratan Fungsional
- Autentikasi admin via daftar Telegram ID pada konfigurasi.
- Penyimpanan data produk, kategori, kupon, transaksi, dan seluruh konfigurasi kustom admin (template pesan, menu, dsb) di database, bukan hardcode.
- Menu admin Telegram memungkinkan admin mengubah template pesan event, kelola produk/order/user, preview sebelum publish, backup & restore konfigurasi, serta audit log.
- Validasi input admin sebelum disimpan, termasuk validasi placeholder pada template pesan.
- Integrasi API Pakasir:
  - Wajib menyimpan `slug`, `api_key`, dan `PAKASIR_PUBLIC_DOMAIN` dalam konfigurasi aman.
  - Mendukung mode sandbox dengan endpoint `paymentsimulation`.
  - Menyimpan `order_id` unik (format `tg{telegram_id}-{timestamp/random}`) untuk korelasi webhook.
- Sistem menyimpan SNK per produk, mengirimkannya otomatis ketika order berstatus `paid/completed`, serta mencatat submission customer (teks/foto) untuk audit.
- Customer dapat mengirim bukti SNK melalui tombol `✅ Penuhi SNK`; bot meneruskan bukti tersebut ke seller/admin dan menandainya sebagai respon SNK.
- Menu admin menyediakan fitur broadcast pesan (teks/foto) ke seluruh user yang pernah `/start`, dengan penanganan user yang diblokir atau memblokir bot.
- Bot mengirim notifikasi order baru ke seluruh seller/admin (kecuali owner) menggunakan daftar `TELEGRAM_OWNER_IDS` untuk pengecualian.
- Logging interaksi, error, dan perubahan konfigurasi di folder `logs/bot-order/YYYY-MM-DD.log`.
- Penanganan error:
  - Jika API Pakasir gagal, tampilkan pesan `⚠️` ke user dan log detail error.
  - Timeout invoice → hapus pesan dan kirim info kadaluarsa sesuai `early_plan.md`.
- Notifikasi admin (opsional) saat stok hampir habis (`≤3`) dengan pesan emoji `🚨`.
- Anti-spam:
  - User tidak boleh mengirim aksi lebih cepat dari 1 detik secara terus menerus.
  - Jika melampaui ambang (puluhan kali secara cepat), bot balas `🚫 Jangan spam ya, tindakanmu akan dilaporkan ke admin.`.
  - Bot mengirim pemberitahuan ke seluruh admin (`telegram_admin_ids`) dengan detail user yang terdeteksi.

## Persyaratan Non-Fungsional
- **Bahasa & Tone**: Bahasa Indonesia baku dengan nuansa santai; setiap respon minimal 3 emoji relevan.
- **Emoji Konsisten**: ReplyKeyboard utama:
  - `📋 List Produk`
  - `📦 Semua Produk`
  - `📊 Cek Stok`
  - `1️⃣`, `2️⃣`, `3️⃣`, dst untuk akses cepat produk.
- **Observability** (mengacu `docs/01_dev_protocol.md`):
  - Format log `[timestamp] [level] message`.
  - Simpan log di `logs/telegram-bot/{date}.log`.
  - Catat metrik ringan (jumlah transaksi, error rate) setiap interval yang wajar.
  - Audit log seluruh perubahan konfigurasi admin (customization, backup/restore, dsb).
- **Struktur Proyek**:
  - `src/` untuk kode utama (mis. `src/bot/`, `src/bot/admin/`, `src/core/custom_config.py`, `src/services/pakasir.py`, `src/core/config.py`).
  - `logs/` sesuai aturan.
  - `tests/` untuk skenario minimal (mock API Pakasir dan custom config).
  - Gunakan virtual environment (Python 3.12+) dan `requirements.txt`.
- **Keandalan**:
  - Semua command bot harus memiliki timeout & fallback pesan `🤖 Maaf, sistem sedang sibuk...`.
  - Hindari loop tanpa jeda; isi dengan `asyncio.sleep`.
  - Idempotensi pada webhook (cek `order_id` sebelum membuat entri baru).
  - Bot dapat rollback ke konfigurasi default jika terjadi error pada konfigurasi kustom.
- **Keamanan**:
  - Simpan kredensial Pakasir via environment (`PAKASIR_PROJECT_SLUG`, `PAKASIR_API_KEY`, `PAKASIR_WEBHOOK_SECRET`).
  - Validasi payload webhook menggunakan signature bila tersedia.
  - Data pribadi buyer/seller dijaga privasinya, hanya admin yang berwenang bisa mengakses.
  - Owner memiliki akses audit penuh dan bisa override jika terjadi masalah.

## Dependensi & Setup (High-Level)
- Bahasa: Python 3.12 (stabil terbaru).
- Library bot: `python-telegram-bot` (versi stabil terbaru).
- HTTP Client: `httpx` atau `aiohttp` untuk panggil API Pakasir.
- Logging: modul `logging` bawaan + rotasi file manual.
- QR: gunakan `qrcode` (opsional) jika perlu generate lokal selain gambar dari Pakasir.
- File pendukung:
  - `requirements.txt` (wajib).
  - `.gitignore` minimal sesuai `project_rules.md`.
  - `README.md` (wajib, panduan pemakaian).

## Jalur Pembayaran (Detail)
1. **Invoice Request**
   - Endpoint: `POST https://app.pakasir.com/api/transactioncreate/qris`.
   - Payload:
     ```json
     {
       "project": "<slug>",
       "order_id": "tg12345-20251102A",
       "amount": 3000,
       "api_key": "<api_key>"
     }
     ```
2. **Response Handling**
   - Ambil `payment.payment_number` (QR string) & `expired_at`.
   - Konversi QR string menjadi gambar atau gunakan domain `https://pots.my.id/pay/...&qris_only=1`.
3. **Webhook**
   - Endpoint internal: `POST /webhooks/pakasir`.
   - Validasi `signature` jika `PAKASIR_WEBHOOK_SECRET` terisi.
   - Update status order (pending → completed), kurangi stok, tambahkan riwayat transaksi user.
   - Kirim pesan sukses ke user dengan emoji `🎉`, `💡`, `🧾`.
4. **Kadaluarsa / Pembatalan**
   - Scheduler cek invoice yang melebihi `expired_at`, hapus dari chat dan kirim pesan kadaluarsa.

## UX Copy & Emoji Guideline
- Gunakan sapaan hangat: `🌟 Halo, <mention_user>!`
- Pesan keranjang: `🧺 Keranjangmu siap dicek!`
- Pesan sukses: `🎉 Pembayaran Berhasil! Terima kasih sudah belanja.`
- Pesan error: `⚠️ Lagi ada kendala nih, coba lagi ya atau hubungi admin.`
- Pastikan minimal satu emoji di setiap baris utama pesan.

## Analytics & Metrics
- Hitung:
  - Jumlah user `/start` total & unik.
  - Total transaksi sukses & gagal.
  - Konversi dari `Lanjut ke Pembayaran` ke pembayaran sukses.
  - Stok terjual per produk.
  - Nilai transaksi per hari.
- Simpan ringkasan harian di log atau basis data untuk analitik lanjutan.

## Risiko & Mitigasi
- **API Pakasir down** → fallback pesan `⚠️` dan catat log error. Sediakan opsi pembayaran manual `💬 Hubungi Admin`.
- **Invoice tidak dihapus** → scheduler harian memastikan pesan invoice lama dibersihkan.
- **Stok tidak sinkron** → gunakan transaksi atomik saat checkout + webhook untuk memastikan stok pas.
- **Penggunaan emoji berlebihan** → definisikan palet emoji per konteks agar konsisten.

## Roadmap (Tahap Awal)
1. Setup kerangka bot + struktur proyek sesuai `docs/01_dev_protocol.md`.
2. Implementasi alur `/start`, daftar produk, detail, dan keranjang.
3. Integrasi Pakasir (sandbox) + webhook.
4. Implementasi admin tools & fitur kustomisasi bot oleh admin (menu Telegram, backup/restore, validasi, audit log).
5. Observability (logging, audit, metrik dasar) + dokumentasi README.

---

> Catatan: Dokumen ini menjadi dasar implementasi awal. Perubahan selanjutnya wajib menjaga konsistensi dengan `docs/00_context.md`, `docs/pakasir.md`, dan `docs/01_dev_protocol.md`.
> Fitur kustomisasi admin, backup/restore, validasi, audit, dan menu admin Telegram wajib dipertahankan sesuai best practice dan aturan project_rules.md.
