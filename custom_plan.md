# Rencana Fitur Kustomisasi Bot oleh Admin (Versi Sederhana)

## Tujuan
Memungkinkan admin (customer) untuk mengatur perilaku utama bot auto order melalui menu Telegram tanpa akses ke codebase, meliputi:
- Respon pesan bot (customizable)
- Pengaturan produk
- Pengelolaan order

## Struktur Menu Utama
- **Admin Settings** (ReplyKeyboardMarkup)
  - Kelola Respon Bot
  - Kelola Produk
  - Kelola Order
  - Kelola User

## Detail Submenu & Fitur

### 1. Kelola Respon Bot
- Admin dapat mengubah template pesan untuk setiap event (order masuk, pembayaran, dsb)
- Fitur preview sebelum publish
- Validasi placeholder (misal: {nama}, {order_id})

### 2. Kelola Produk
- CRUD produk via menu
- Upload gambar produk (jika didukung)

### 3. Kelola Order
- Lihat daftar order
- Update status order

### 4. Kelola User
- Lihat user yang pernah order
- Blokir/unblokir user

## Best Practice (Tidak Merugikan Seller, Buyer, Admin, Owner)
- Semua perubahan disimpan di database, bukan hardcode
- Validasi input admin sebelum disimpan
- Fitur backup & restore konfigurasi
- Logging setiap perubahan konfigurasi untuk audit
- UI/UX menu Telegram dibuat intuitif & mudah dipahami
- Bot harus bisa rollback ke default jika terjadi error konfigurasi
- Data pribadi buyer/seller dijaga privasinya, hanya admin yang berwenang bisa mengakses
- Owner memiliki akses audit penuh dan bisa override jika terjadi masalah
- Semua transaksi dan perubahan penting harus ada notifikasi ke owner
- Fitur keamanan seperti rate limit, anti-spam, dan validasi data diterapkan
