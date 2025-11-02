# Product Requirements Document – Bot Auto Order Telegram

## Referensi
- `early_plan.md` – gambaran alur interaksi pengguna dan admin.
- `pakasir.md` – panduan integrasi payment gateway Pakasir.
- `project_rules.md` – aturan struktur proyek, observability, dan praktik kolaborasi.

## Ringkasan
Bot Telegram auto-order untuk toko digital dengan pembayaran terhubung Pakasir. Menggunakan bahasa Indonesia baku bernuansa santai; setiap respons bot wajib kaya emoji agar terasa hidup. Admin dapat mengelola produk, kategori, dan pesan balasan kustom langsung dari bot.

## Tujuan
- Mempermudah pembeli memesan produk digital via Telegram secara mandiri.
- Menyediakan jalur pembayaran otomatis melalui Pakasir (khususnya QRIS).
- Menjamin admin dapat memantau stok, transaksi, dan saldo pengguna dari satu antarmuka bot.

## Target Pengguna
- **Pembeli**: pengguna Telegram yang ingin membeli produk digital dengan proses cepat dan jelas.
- **Admin**: pemilik toko yang mengatur katalog, stok, harga, kupon, dan saldo pengguna.

## Ruang Lingkup Fitur
1. **Onboarding `/start`**  
   - Pesan sambutan bergaya emoji dan menyertakan statistik total user & transaksi.  
   - Inline keyboard kategori (termasuk `🧭 Semua Produk`) dan ReplyKeyboard utama (`📋 List Produk`, `📦 Semua Produk`, `📊 Cek Stok`, `1️⃣`, `2️⃣`, `3️⃣`, dst).
2. **Navigasi Produk**  
   - Inline keyboard menampilkan kategori serta daftar produk menurut `early_plan.md`.  
   - Format setiap produk memuat nama, harga, stok, total penjualan, emoji tematik (mis. `🔥`, `🎟️`, `💾`).
3. **Detail Produk & Cart**  
   - Pesan detail produk memuat harga, stok, kategori dengan emoji (contoh: `🛒`, `💲`, `📦`).  
   - Inline keyboard tindakan (`➖`, `➕`, `🧺 Lanjut ke Keranjang`, `❌ Batal`) dan opsi kuantitas (`✌️ x2`, `🖐️ x5`, `🔟 x10`).
4. **Keranjang Belanja**  
   - Ringkasan item dengan pembuka emoji (`⛺`, `🧾`) dan peringatan pembayaran (`🚫`).  
   - Inline keyboard (`🎟️ Gunakan Kupon`, `💳 Lanjut ke Pembayaran`, `❌ Batal`).
5. **Pembayaran via Pakasir**  
   - Langkah memilih metode (`🧊 Silakan Pilih Metode Pembayaran`) dengan tombol `💠 QRIS`, `💼 Saldo`, `❌ Batalkan`.  
   - Integrasi API Pakasir `transactioncreate` (metode `qris`) atau URL `https://pots.my.id/pay/{slug}/{amount}?order_id={order_id}&qris_only=1`.  
   - Penanganan loading (`🎲 Sedang memuat...`) dan invoice sukses (`🏷️ Invoice Berhasil Dibuat`).  
   - Pengelolaan kadaluarsa: hapus pesan invoice, kirim stiker, dan notifikasi `📜 Tagihan Kadaluarsa`.
6. **Saldo & Deposit**  
   - Reply keyboard `💼 Deposit` untuk opsi manual (admin input) atau otomatis via Pakasir.  
   - Riwayat saldo ditampilkan dengan emoji status (`✅`, `⏳`, `❌`).
7. **Kupon & Diskon**  
   - Opsi `🎟️ Gunakan Kupon` sebelum pembayaran, validasi langsung di bot.
8. **Admin Tools**  
   - Pembuatan kategori, produk, stok, harga, dan deskripsi.  
   - Pengaturan ReplyKeyboard kustom beserta jawaban (contoh `📘 Cara Order`).  
   - Dashboard ringkas via command admin (`/admin`, `⚙️ Pengaturan`).

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

## Persyaratan Fungsional
- Autentikasi admin via daftar Telegram ID pada konfigurasi.
- Penyimpanan data produk, kategori, kupon, dan transaksi (gunakan storage sesuai arsitektur lanjutan).
- Integrasi API Pakasir:
  - Wajib menyimpan `slug`, `api_key`, dan `PAKASIR_PUBLIC_DOMAIN` dalam konfigurasi aman.
  - Mendukung mode sandbox dengan endpoint `paymentsimulation`.
  - Menyimpan `order_id` unik (format `tg{telegram_id}-{timestamp/random}`) untuk korelasi webhook.
- Logging interaksi dan error di folder `logs/bot-order/YYYY-MM-DD.log`.
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
- **Observability** (mengacu `project_rules.md`):
  - Format log `[timestamp] [level] message`.
  - Simpan log di `logs/telegram-bot/{date}.log`.
  - Catat metrik ringan (jumlah transaksi, error rate) setiap interval yang wajar.
- **Struktur Proyek**:
  - `src/` untuk kode utama (mis. `src/bot/`, `src/services/pakasir.py`, `src/core/config.py`).
  - `logs/` sesuai aturan.
  - `tests/` untuk skenario minimal (mock API Pakasir).
  - Gunakan virtual environment (Python 3.12+) dan `requirements.txt`.
- **Keandalan**:
  - Semua command bot harus memiliki timeout & fallback pesan `🤖 Maaf, sistem sedang sibuk...`.
  - Hindari loop tanpa jeda; isi dengan `asyncio.sleep`.
  - Idempotensi pada webhook (cek `order_id` sebelum membuat entri baru).
- **Keamanan**:
  - Simpan kredensial Pakasir via environment (`PAKASIR_PROJECT_SLUG`, `PAKASIR_API_KEY`, `PAKASIR_WEBHOOK_SECRET`).
  - Validasi payload webhook menggunakan signature bila tersedia.

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
1. Setup kerangka bot + struktur proyek sesuai `project_rules.md`.
2. Implementasi alur `/start`, daftar produk, detail, dan keranjang.
3. Integrasi Pakasir (sandbox) + webhook.
4. Implementasi admin tools & custom reply.
5. Observability (logging & metrik dasar) + dokumentasi README.

---

> Catatan: Dokumen ini menjadi dasar implementasi awal. Perubahan selanjutnya wajib menjaga konsistensi dengan `early_plan.md`, `pakasir.md`, dan `project_rules.md`.
