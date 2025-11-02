# Rencana Awal Bot Auto Order Telegram

## Gambaran Umum
- Bot Telegram untuk auto order produk, terhubung ke payment gateway.
- Fokus utama: alur pembelian otomatis dari `/start` sampai pembayaran.

## Salam Awal (`/start`)
- Pesan sambutan:
  ```
  — Hai, **<mention_user>** 👋🏻

  Selamat datang di <nama_toko>
    • Total User Bot: 🙍🏻‍♂️ 4673 Orang
    • Total Transaksi Terselesaikan: 2383341x
  ```
  - Total user = jumlah user yang pernah mengirim `/start`.
  - Total transaksi = total transaksi yang berhasil.
- Arahkan pengguna untuk menekan tombol guna melihat daftar produk.
- Inline keyboard menampilkan kategori dan produk yang dibuat admin, plus tombol `Semua Produk`.
- ReplyKeyboardMarkup bawaan:
  - `List Produk`, `Stok`, `1`, `2`, `3`, dst.
  - Nomor (`1`, `2`, `3`, ...) mereferensikan urutan produk.

## Tampilan Daftar Produk (Contoh dari `Semua Produk`)
- Format produk:
  ```
  13. netflix premium 1p1u 1 bln = Rp50000
  <deskripsi> (default: tidak ada deskripsi untuk produk ini)
  Stok ➜ x12
  Terjual ➜ 344x
  ```
- Contoh lain:
  ```
  14. netflix premium 1p2u 1 bln = Rp25000
  <deskripsi>
  Stok ➜ x5
  Terjual ➜ 120x
  ```
- Produk seterusnya mengikuti format serupa.

## Detail Produk & Keranjang
- Ketika user memilih produk via reply keyboard angka (misal `3`):
  ```
  ⌊ capcut private 7d ⌉
  Tidak ada deskripsi untuk produk ini

  + Harga: Rp 3.000,00
  + Stok Tersedia: 6x
  + Category: Uncategory

  Tekan tombol + untuk menambahkan item
  ini ke dalam cart dan melakukan checkout
  ```
  - Inline keyboard: `-`, `+`, `Lanjut ke keranjang`, `Cancel`.
- Saat user menekan `+`:
  ```
  ⌊ capcut private 7d ⌉
  Tidak ada deskripsi untuk produk ini

  + Harga Satuan: Rp 3.000,00
  + Stok Tersedia: 6

  + In Cart: 1x
  + Total Dibayar: Rp 3.000,00

  Tekan tombol + untuk menambahkan item
  ini ke dalam cart dan melakukan checkout
  ```
  - Inline keyboard berubah menjadi: `-`, `+`, `x2`, `x5`, `x10`, `Lanjut ke keranjang`, `Cancel`.
- Setelah `Lanjut ke keranjang`:
  ```
  ⛺ Keranjang Belanja kamu
  Pastikan jumlah item dan harga sudah benar
  --------------------------------
  × Total Item: 1
  × Total Dibayar: Rp 3.000,00

  3. capcut private 7d x1 = Rp 3.000,00

  Kami tidak menerima complain jika sudah melakukan pembayaran
  terkait perbedaan harga atau jumlah item
  ```
  - Inline keyboard: `Gunakan Kupon`, `Lanjut ke pembayaran`, `Cancel`.

## Alur Pembayaran
- Setelah `Lanjut ke pembayaran`:
  ```
  🧊 Silahkan Pilih Metode Pembayaran

  Informasi Tagihan
  — Total Dibayar: Rp 3.000,00
  - Date Created: 02/11/25

  Informasi Kamu
  — Name: <nama_pembeli>
  — Saldo Kamu: Rp 0,00
  — Bank Id: 524107
  — User ID: <telegram_id_pembeli>
  ```
  - Inline keyboard: `qris`, `balance`, `batalkan pembelian`.
- Jika user memilih `qris`:
  1. Pesan loading: `🎲 Sedang Memuat Pembayaranmu, Harap tunggu sebentar...`.
  2. Kirim gambar QR + detail invoice:
     ```
     🏷️ Invoice Berhasil Dibuat
     RESS1762100133206

     Informasi Item:
     — Item Price Total: Rp 4.000,00
     — Jumlah Item: 1x
     — List Yang Dibeli:
     1. capcut private 7d x1 = Rp 4.000,00

     Informasi Pembayaran:
     — ID Transaksi: RESS1762100133206
     — Tanggal Dibuat: 02/11/25
     — Total Dibayar: Rp 3.000,00
     — Expired In: 5 Menit
     ```
     - Inline keyboard: `checkout url` (mini app), `batalkan pembelian`.
- Jika pembayaran sukses: kirim detail produk, S&K, dst sesuai template admin.
- Jika gagal / kadaluarsa: hapus pesan invoice dan kirim:
  ```
  <sticker>
  📜 Tagihan Kadaluarsa
  RESS1762100133206

  Tagihan kamu dengan detail invoice berikut telah kadaluarsa
  kamu bisa melakukan pembelian ulang untuk
  mendapatkan tagihan qris baru
  ```

## Fitur Admin
- Membuat kategori dan produk untuk inline keyboard.
- Menambah ReplyKeyboardMarkup custom + respon yang dikaitkan.
  - Contoh: tombol `Cara Order` → balasan teks yang diatur admin.
- Menu `Deposit` di reply keyboard:
  - Manual: buyer transfer via private chat, admin input saldo user ke bot.
  - Otomatis: terhubung ke payment gateway.
