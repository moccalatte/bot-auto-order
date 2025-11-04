# Frontend / UIUX Bot Auto Order

Dokumen ini mensimulasikan tampilan dan alur interaksi bot Telegram tanpa benar-benar menjalankannya. Seluruh teks dan struktur mengikuti emoji, label tombol, dan respon yang ada di kode saat ini. Anggap setiap langkah berupa percakapan antara pengguna dengan bot.

---

## 1. Persona & Akses
- **Pelanggan**: siapa pun yang memulai percakapan dengan bot. Melihat katalog, stok, keranjang, pembayaran.
- **Admin**: pengguna yang ID Telegram-nya terdaftar di `TELEGRAM_ADMIN_IDS`. Mendapat menu tambahan “⚙️ Admin Settings”.

---

## 2. Alur Onboarding / Start
1. Pengguna kirim `/start`.
2. Bot membalas:
   ```
   🌟 Hai, **{nama depan}**! 👋🏻
   🎪 Selamat datang di **{store_name}**
   🙍🏻‍♂️ Total Sahabat Bot: {total_users}
   💼 Transaksi Tuntas: {total_transactions}

   🛒 Silakan pakai tombol di bawah untuk jelajahi katalog kami!
   ```
3. Bot menampilkan **Reply Keyboard utama**:
   - Baris 1: `📋 List Produk` | `📦 Semua Produk`
   - Baris 2: `📊 Cek Stok` | `💼 Deposit`
   - Baris 3: `🧮 Calculator`
   - Baris 4: daftar angka `{1️⃣, 2️⃣, ...}` sesuai jumlah produk (maks 6).
4. Bot mengirim keyboard **Inline Kategori**:
   - Tombol berbasis kategori: contoh `🍿 Snack`, `🧃 Minuman`.
   - Tombol terakhir: `🧭 Semua Produk`.

---

## 3. Alur Pelanggan

### 3.1. Melihat Kategori
- Pengguna menekan tombol kategori (inline).
- Bot memuat produk dalam kategori, mengirim pesan:
  ```
  🧾 Daftar Produk {kategori}
  --------------------------------
  1. Produk A = Rp xx.xxx
  📝 Deskripsi...
  📦 Stok ➜ x10
  🔥 Terjual ➜ 25x
  🍿 Kategori ➜ Snack
  --------------------------------
  ```
- Daftar maksimal 10 item sekaligus.
- Bot menyimpan list produk di `user_data`.

### 3.2. Melihat Detail Produk
1. Pengguna menekan angka di keyboard (misal `1️⃣`).
2. Bot menampilkan detail:
   ```
   ⌊ Produk A ⌉
   🗒️ Deskripsi...

   💲 Harga: Rp xx.xxx
   📦 Stok Tersedia: x10
   🍿 Category: Snack

   ➕ Tekan tombol untuk menambahkan item ke keranjang dan lanjut checkout.
   ```
3. Inline keyboard produk:
   - Baris 1: `➖` | `➕`
   - Baris 2 (muncul bila quantity > 0): `✌️ x2` | `🖐️ x5` | `🔟 x10`
   - Baris 3: `🧺 Lanjut ke Keranjang` | `❌ Batal`

### 3.3. Mengelola Keranjang
1. Menekan `➕` / `➖` / preset qty memperbarui jumlah, bot mengedit pesan detail dengan kuantitas baru dan respon singkat (misal “🛒 Ditambahkan!”).
2. `🧺 Lanjut ke Keranjang` → bot mengirim ringkasan:
   ```
   ⛺ Keranjang Belanja Kamu
   ✅ Pastikan jumlah item...
   --------------------------------
   📦 Total Item: 3
   💵 Total Dibayar: Rp xx.xxx

   Produk A x3 ... (dll)

   🚫 Kami tidak menerima komplain setelah pembayaran selesai.
   ```
3. Inline keyboard keranjang:
   - Baris 1: `🎟️ Gunakan Kupon` | `💳 Lanjut ke Pembayaran`
   - Baris 2: `❌ Batal`

### 3.4. Pembayaran
- `🎟️ Gunakan Kupon`: saat ini hanya pesan placeholder “Fitur kupon akan segera hadir”.
- `💳 Lanjut ke Pembayaran`: bot mengirim prompt:
  ```
  🧊 Silakan Pilih Metode Pembayaran
  💳 Informasi Tagihan
  — Total Dibayar: Rp xx.xxx
  ...
  ```
- Inline keyboard pembayaran:
  - Baris 1: `💠 QRIS` | `💼 Saldo`
  - Baris 2: `❌ Batalkan Pembelian`
- `💠 QRIS` → bot menampilkan pesan “Sedang memuat pembayaranmu...”, lalu invoice:
  - Jika QR tersedia, bot mengirim foto QR, caption invoice, dan tombol `🔗 Checkout URL`.
- `💼 Saldo`: placeholder “Saldo belum tersedia.”
- `❌ Batalkan Pembelian`: keranjang dikosongkan, pesan pembatalan.

### 3.5. Fitur Lain di Menu Utama
- `📋 List Produk`: menampilkan daftar semua produk dengan format sama seperti kategori.
- `📦 Semua Produk`: men-trigger inline kategori “Semua Produk”.
- `📊 Cek Stok`: menampilkan 10 produk teratas dengan format:
  ```
  Produk A • 📦 12x • 🔥 30x
  ```
- `💼 Deposit`: info singkat cara deposit manual / QRIS.
- `🧮 Calculator`: memuat isi `calcu.md` lalu menampilkan rumus refund + instruksi lanjutan.

### 3.6. Anti-Spam & Blokir
- Jika pengguna menekan terlalu cepat, bot bisa membalas peringatan (sesuai modul antispam).
- Jika akun diblokir admin, semua interaksi dibalas:
  ```
  ❌ Akun kamu sedang diblokir oleh admin. Hubungi admin untuk bantuan.
  ```

---

## 4. Alur Admin: Menu “⚙️ Admin Settings”

### 4.1. Akses
- Admin menekan tombol `⚙️ Admin Settings`.
- Bot memverifikasi ID admin. Jika bukan admin → “❌ Kamu tidak punya akses admin.”
- Admin menerima menu reply:
  - `🛠 Kelola Respon Bot`
  - `🛒 Kelola Produk`
  - `📦 Kelola Order`
  - `👥 Kelola User`
  - `⬅️ Kembali ke Menu Utama`

### 4.2. Kelola Respon Bot
1. Menekan `🛠 Kelola Respon Bot` → bot mengirim inline keyboard:
   - `👁️ Preview Semua Respon`
   - `⬅️ Kembali`
2. Admin hanya dapat melakukan **preview** template aktif; perubahan dilakukan oleh owner di luar menu bot.
3. `⬅️ Kembali` → kembali ke menu utama Admin Settings.

### 4.3. Kelola Produk
1. Tombol `🛒 Kelola Produk` menampilkan ringkasan produk aktif (limit 10) dan inline keyboard:
   - `➕ Tambah Produk`
   - `📝 Edit Produk`
   - `🗑️ Hapus Produk`
   - `⬅️ Kembali`
2. Flow tiap aksi:
   - **Tambah Produk**: bot menampilkan format input `kategori_id|kode|nama|harga|stok|deskripsi`. Admin balas teks → produk dibuat → balasan sukses. Gambar tidak dapat diunggah dari menu ini.
   - **Edit Produk**: format `produk_id|field=value,...` (field: name, description, price, stock, code, category_id). Balasan sukses atau error validasi.
   - **Hapus Produk**: admin balas ID → bot hapus dan kirim konfirmasi.
   - `⬅️ Kembali`: ke Admin Settings.

### 4.4. Kelola Order
1. Tombol `📦 Kelola Order` menampilkan daftar order terbaru (ID, status, total) dan inline:
   - `📋 Lihat Daftar Order` (terpenuhi by default lewat ringkasan)
   - `🔄 Update Status Order`
   - `⬅️ Kembali`
2. `🔄 Update Status Order`: bot meminta format `order_id|status_baru` → update DB → konfirmasi.

### 4.5. Kelola User
1. Tombol `👥 Kelola User` menampilkan daftar user terbaru (ID, username, telegram_id, status blokir) dan inline:
   - `👥 Lihat User`
   - `🚫 Blokir User`
   - `✅ Unblokir User`
   - `⬅️ Kembali`
2. `🚫 Blokir User`: bot minta ID user → update kolom `is_blocked` → konfirmasi.
3. `✅ Unblokir User`: format sama, status diubah ke aktif.

### 4.6. Kelola Voucher
1. Reply keyboard khusus:
   - `➕ Generate Voucher Baru`
   - `📋 Lihat Voucher Aktif`
   - `🗑️ Nonaktifkan/Hapus Voucher`
   - `⬅️ Kembali ke Admin Settings`
2. Flow:
   - **Generate Voucher**: input `kode|deskripsi|tipe|nilai|max_uses|valid_from|valid_until`. Gunakan `-` untuk kolom opsional. Bot mencatat aksi di log owner.
   - **Lihat Voucher Aktif**: bot menampilkan daftar voucher beserta tipe, nominal diskon, max penggunaan, dan rentang validitas.
   - **Nonaktifkan/Hapus Voucher**: admin mengirim ID voucher → voucher dinonaktifkan, aksi tercatat di log.
   - `⬅️ Kembali ke Admin Settings`: kembali ke menu utama admin.

### 4.7. Navigasi Kembali & Catatan Penting
- `⬅️ Kembali ke Menu Utama` (reply) → bot menampilkan keyboard pengguna biasa lagi (List Produk, dll).
- `⬅️ Kembali` pada inline submenu → kembali ke daftar menu admin.
- Saat memperbarui status order, admin menggunakan format `order_id|status|catatan(optional)`; catatan hanya diisi bila pembayaran manual/deposit dan cukup berisi bukti singkat.

---

## 5. Kasus Kesalahan & Validasi
- Format input tidak sesuai → pesan error seperti `❌ Format tidak valid...`.
- Placeholder tidak valid pada template → error dari validator placeholder.
- ID tidak ditemukan (produk/order/user/voucher) → pesan “tidak ditemukan”.
- Kesalahan internal (misal DB) → log + pesan `⚠️ Terjadi kesalahan internal, coba lagi.`.

---

## 6. Ringkasan Alur
| Persona | Langkah Kunci                         | Output UI                                  |
|---------|---------------------------------------|---------------------------------------------|
| Pelanggan | /start → pilih produk → keranjang → pembayaran | Reply keyboard, detail produk, invoice |
| Admin | ⚙️ Admin Settings → pilih submenu → ikuti format | Inline/reply keyboard khusus + instruksi |

Dokumen ini dapat dijadikan referensi desain UI sederhana (misal mockup wireflow) tanpa harus menjalankan bot sebenarnya. Semua teks sudah mengikuti bahasa & nada yang ada di implementasi. Seluruh jalur input maupun keluaran error telah dicakup. 
