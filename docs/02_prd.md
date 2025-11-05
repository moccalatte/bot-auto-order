# Product Requirements Document – Bot Auto Order Telegram

> **Version:** 0.2.2 | **Last Updated:** 2025-01-16 | **Status:** ✅ Production Ready

## Referensi
- `docs/00_context.md` – gambaran alur interaksi pengguna dan admin.
- `docs/pakasir.md` – panduan integrasi payment gateway Pakasir.
- `docs/01_dev_protocol.md` – aturan struktur proyek, observability, dan praktik kolaborasi.
- `docs/CHANGELOG.md` – riwayat perubahan dan release notes.
- `docs/core_summary.md` – ringkasan inti proyek dan status modul.

## Ringkasan
Bot Telegram auto-order untuk toko digital dengan pembayaran terhubung Pakasir. Menggunakan bahasa Indonesia baku bernuansa santai; setiap respons bot wajib kaya emoji agar terasa hidup. Bot menggunakan **HTML parse mode** untuk formatting yang lebih baik dengan bold, italic, dan code tags. Admin dapat mengelola produk, kategori, pesan balasan kustom, dan konfigurasi utama bot langsung dari **menu hierarkis** di Telegram tanpa akses ke codebase. Bot menampilkan **role-based keyboard** yang berbeda untuk admin dan customer.

## Tujuan
- Mempermudah pembeli memesan produk digital via Telegram secara mandiri.
- Menyediakan jalur pembayaran otomatis melalui Pakasir (khususnya QRIS).
- Menjamin admin dapat memantau stok, transaksi, dan saldo pengguna dari satu antarmuka bot.

## Target Pengguna
- **Pembeli**: pengguna Telegram yang ingin membeli produk digital dengan proses cepat dan jelas.
- **Admin**: pemilik toko yang mengatur katalog, stok, harga, kupon, saldo pengguna, serta kustomisasi respon bot dan pengaturan utama melalui menu admin Telegram.

## Ruang Lingkup Fitur

### Customer Features
1. **Onboarding `/start`**
   - **Sticker engaging** dikirim terlebih dahulu untuk better user experience.
   - Pesan sambutan dengan **HTML formatting** (bold untuk nama user dan statistik).
   - Statistik real-time: Total Pengguna Bot dan Transaksi Tuntas dengan bold formatting.
   - Inline keyboard kategori (termasuk 🧭 Semua Produk) dan ReplyKeyboard berbasis role.
   - **Role-based keyboard**: Admin melihat `⚙️ Admin Settings`, customer melihat keyboard standar.
   - **Auto user tracking**: Setiap `/start` otomatis menjalankan `upsert_user()` untuk statistics.
2. **Navigasi Produk**
   - Inline keyboard menampilkan kategori serta daftar produk.
   - **HTML formatting**: Nama produk, harga, dan stok menggunakan bold tags (`<b>`).
   - Format setiap produk memuat nama, harga, stok, total penjualan, emoji tematik (mis. 🔥, 🎟️, 💾).
3. **Detail Produk & Cart**
   - Pesan detail produk dengan **HTML formatting**: field labels (Nama, Harga, Stok, Kategori) menggunakan bold.
   - Inline keyboard tindakan (➖, ➕, 🧺 Lanjut ke Keranjang, ❌ Batal) dan opsi kuantitas (✌️ x2, 🖐️ x5, 🔟 x10).
4. **Keranjang Belanja**
   - Ringkasan item dengan **bold pada totals** dan item counts.
   - Inline keyboard (🎟️ Gunakan Kupon, 💳 Lanjut ke Pembayaran, ❌ Batal).
5. **Pembayaran via Pakasir**
   - Langkah memilih metode dengan tombol 💠 QRIS, 💼 Saldo, ❌ Batalkan.
   - **HTML formatting**: Invoice ID dan amount menggunakan `<code>` tags untuk easy copy-paste.
   - Integrasi API Pakasir `transactioncreate` (metode `qris`) atau URL `https://pots.my.id/pay/{slug}/{amount}?order_id={order_id}&qris_only=1`.
   - Penanganan loading (🎲 Sedang memuat...) dan invoice sukses (🏷️ Invoice Berhasil Dibuat) dengan bold formatting.
   - Pengelolaan kadaluarsa: hapus pesan invoice, kirim stiker, dan notifikasi 📝 Tagihan Kadaluarsa.
6. **Saldo & Deposit**
   - Opsi manual (admin input) atau otomatis via Pakasir.
   - Riwayat saldo ditampilkan dengan emoji status (✅, ⏳, ❌) dan HTML formatting.
7. **Kupon & Diskon**
   - Opsi 🎟️ Gunakan Kupon sebelum pembayaran, validasi langsung di bot.

### Admin Features (Role-Based Access)
8. **Admin Menu Hierarkis `⚙️ Admin Settings`**
   - **Main Menu** dengan 9 submenu terorganisir menggunakan inline keyboards:
     - 📝 **Kelola Respon Bot**:
       - Preview semua template messages (welcome, product, cart, payment, error, success, SNK)
       - Edit template teks dengan placeholder validation (`{nama}`, `{order_id}`, etc.)
       - Upload gambar untuk templates
       - Cancel button pada setiap mode input
     - 📦 **Kelola Produk**:
       - CRUD products dengan statistics lengkap
       - HTML formatted product details
     - 📋 **Kelola Order**:
       - View dan update order status
       - Filtering dan search functionality
     - 👥 **Kelola User**:
       - User statistics dashboard (total, active, blocked)
       - User list dengan pagination
       - Block/unblock functionality dengan confirmation
       - User detail view dengan transaction history
     - 🎟️ **Kelola Voucher**:
       - Generate vouchers dengan format user-friendly (nominal/persentase/custom)
       - Input validation dan error messages
       - Cancel button untuk abort creation
     - 📢 **Broadcast**:
       - Send messages (text/photo) ke semua users
       - Real-time statistics (total, success, failed counts)
       - Cancel button untuk abort mid-process
       - Automatic handling untuk users yang block bot
     - 🧮 **Calculator**:
       - User-friendly inline keyboard untuk input nominal
       - Support refund dan deposit calculations
       - Clear visual feedback
     - 📊 **Statistik**:
       - Comprehensive dashboard dengan bot metrics
       - HTML formatted statistics
     - 💰 **Deposit**:
       - Manage user deposits dengan inline buttons
   - **Role Detection**: Admin IDs dari `TELEGRAM_ADMIN_IDS` otomatis mendapat akses penuh.
   - **Access Control**: Customer users tidak melihat admin menu.
9. **SNK Produk & Monitoring**
   - Admin dapat menambahkan Syarat & Ketentuan (SNK) khusus per produk.
   - Bot mengirim SNK otomatis setelah pembayaran sukses dengan HTML formatting.
   - Tombol `✅ Penuhi SNK` untuk customer mengirim bukti (teks/foto).
   - Bukti diteruskan ke admin dengan audit log lengkap.
10. **Notifikasi Pesanan ke Seller**
    - Setiap order baru menerbitkan notifikasi otomatis ke daftar admin (tanpa owner).
    - Notifikasi dengan HTML formatting untuk readability.

## Alur Pengguna (Ringkas)

### Customer Flow
1. `User` kirim `/start` → Bot kirim **sticker** terlebih dahulu, kemudian sambutan dengan **HTML formatting** (bold pada nama dan statistik) + inline kategori dan **role-based reply keyboard**.
   - **Auto tracking**: `upsert_user()` dipanggil untuk update statistics.
2. `User` pilih kategori atau `🧭 Semua Produk` → Bot kirim daftar produk dengan **HTML formatting** (bold pada nama produk dan harga).
3. `User` pilih produk (via nomor di reply keyboard atau inline) → Bot kirim detail dengan **bold field labels** + tombol `➕`.
4. `User` tambahkan produk (kondisi stok dicek) → Bot update pesan dengan jumlah di keranjang.
5. `User` klik `🧺 Lanjut ke Keranjang` → Bot tampilkan ringkasan dengan **bold totals**, opsi kupon, lanjut bayar.
6. `User` pilih `💳 Lanjut ke Pembayaran` → Bot kirim pilihan metode (default `💠 QRIS`).
7. `User` pilih QRIS → Bot panggil API Pakasir, tampilkan QR & link mini app dengan **code tags pada invoice ID**.
   - Jika sukses: tampilkan pesan sukses dengan **bold formatting** + detail produk & S&K (emoji `🎉`, `📦`).
   - Jika kadaluarsa: hapus invoice, kirim stiker + pesan `📜 Tagihan Kadaluarsa`.
8. Setelah status order `paid/completed` → Bot mengirim pesan SNK (per produk) ke customer beserta tombol `✅ Penuhi SNK`. Customer yang menekan tombol dapat mengirim bukti dan keterangan; bot mencatat dan meneruskan informasi ke seller/admin (owner dikecualikan).

### Admin Flow
1. `Admin` kirim `/start` → Bot deteksi role, tampilkan **admin keyboard** dengan `⚙️ Admin Settings` button.
2. `Admin` klik `⚙️ Admin Settings` → Bot tampilkan **main menu** dengan 9 submenu (inline keyboard).
3. `Admin` pilih submenu (e.g., 📢 Broadcast):
   - Input message (text atau upload photo)
   - Bot tampilkan **real-time statistics** (total, success, failed)
   - **Cancel button** tersedia setiap saat untuk abort
4. `Admin` complete operation → Bot tampilkan summary dengan **HTML formatting** dan return ke main menu.

## Persyaratan Fungsional

### Core Functionality
- **Role-Based Access Control**:
  - Autentikasi admin via `TELEGRAM_ADMIN_IDS` di konfigurasi
  - Bot otomatis deteksi role dan tampilkan keyboard yang sesuai
  - Admin melihat `⚙️ Admin Settings`, customer tidak
- **Auto User Tracking**:
  - Setiap `/start` command otomatis menjalankan `upsert_user()`
  - Statistics (total users, transactions) update real-time
  - Database tracking lengkap untuk audit
- **HTML Parse Mode**:
  - ALL message templates menggunakan HTML formatting
  - Bold (`<b>`) untuk important info (names, prices, totals, field labels)
  - Italic (`<i>`) untuk disclaimers dan notes
  - Code tags (`<code>`) untuk IDs dan copyable data
  - Consistent emoji usage untuk visual hierarchy
- **Clean Message Flow**:
  - Tidak ada redundant messages
  - Keyboard langsung attached ke main message
  - Single welcome message dengan keyboard

### Data Management
- Penyimpanan data produk, kategori, kupon, transaksi, dan seluruh konfigurasi kustom admin (template pesan, menu, dsb) di database PostgreSQL, bukan hardcode.
- Database schema support untuk user tracking, statistics, dan audit logs.

### Admin Menu (Hierarchical Structure)
- **Main Menu `⚙️ Admin Settings`** dengan inline keyboard navigation
- **9 Organized Submenus** dengan proper callbacks dan state management:
  - Kelola Respon Bot: Preview, edit templates, upload images, placeholder validation
  - Kelola Produk: CRUD dengan statistics
  - Kelola Order: View, update status, filtering
  - Kelola User: Statistics, pagination, block/unblock
  - Kelola Voucher: Generation dengan format user-friendly
  - Broadcast: Send messages dengan real-time stats
  - Calculator: Inline keyboard input untuk calculations
  - Statistik: Comprehensive dashboard
  - Deposit: User deposit management
- **Cancel Buttons**: Semua critical input modes dapat di-cancel
- **Real-Time Feedback**: Operations menampilkan live statistics
- Validasi input admin sebelum disimpan, termasuk validasi placeholder pada template pesan.
- Backup & restore konfigurasi dengan audit log.

### Payment Integration
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

### UX & Design
- **Bahasa & Tone**: Bahasa Indonesia baku dengan nuansa santai; setiap respon minimal 3 emoji relevan.
- **HTML Formatting Standards**:
  - `<b>bold</b>` untuk informasi penting (user names, store name, prices, totals, field labels)
  - `<i>italic</i>` untuk disclaimers, notes, dan keterangan
  - `<code>code</code>` untuk IDs dan data yang perlu di-copy (invoice IDs, transaction IDs)
  - Consistent emoji usage untuk visual hierarchy
  - `parse_mode=ParseMode.HTML` di semua handler functions
- **Role-Based Keyboard**:
  - Admin: `⚙️ Admin Settings | 📋 List Produk | 🛍 Semua Produk | 🏷 Cek Stok | 1️⃣ | 2️⃣ | 3️⃣ | ...`
  - Customer: `📋 List Produk | 🛍 Semua Produk | 🏷 Cek Stok | 1️⃣ | 2️⃣ | 3️⃣ | ...`
- **Engagement**: Sticker dikirim saat `/start` sebelum welcome message
- **Clean Flow**: No redundant messages, keyboard attached langsung

### Observability
- **Logging** (mengacu `docs/01_dev_protocol.md`):
  - Format log `[timestamp] [level] message`.
  - Simpan log di `logs/telegram-bot/{date}.log`.
  - Enhanced logging untuk admin actions dengan user ID dan action type.
  - Catat metrik ringan (jumlah transaksi, error rate) setiap interval yang wajar.
- **Audit Log**:
  - Seluruh perubahan konfigurasi admin (customization, backup/restore, dsb)
  - User tracking (upsert operations)
  - Broadcast operations dengan statistics
  - SNK submissions dari customers
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
  ## Keamanan & Privacy**:
    - Simpan kredensial Pakasir via environment (`PAKASIR_PROJECT_SLUG`, `PAKASIR_API_KEY`, `PAKASIR_WEBHOOK_SECRET`).
    - Config validators untuk `TELEGRAM_ADMIN_IDS` dan `TELEGRAM_OWNER_IDS` (support single integer dan comma-separated strings).
    - Validasi payload webhook menggunakan signature bila tersedia.
    - Input validation dan sanitization untuk semua admin inputs (no SQL injection).
    - Role-based access control: hanya admin yang dapat akses admin menu.
    - Data pribadi buyer/seller dijaga privasinya, hanya admin yang berwenang bisa mengakses.
    - Owner memiliki akses audit penuh dan bisa override jika terjadi masalah.
    - Audit log untuk tracking semua admin actions dan user operations.

## Dependensi & Setup (High-Level)
- **Bahasa**: Python 3.12+
- **Library bot**: `python-telegram-bot[webhooks,job-queue]==21.3` - Full support untuk webhooks, polling, dan scheduled tasks
- **HTTP Client**: `httpx` atau `aiohttp` untuk panggil API Pakasir
- **Database**: PostgreSQL 15+ untuk data persistence dan user tracking
- **Logging**: modul `logging` bawaan + rotasi file manual + audit logger
- **QR**: gunakan `qrcode` (opsional) jika perlu generate lokal selain gambar dari Pakasir
- **Encryption**: `cryptography` untuk enkripsi data SNK
- **JobQueue**: Background tasks untuk SNK dispatch, broadcast queue, health checks
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
