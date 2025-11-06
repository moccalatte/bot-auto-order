## Rencana Perbaikan Masalah (Update 0.5.3 – 2025-11-07)

Seluruh 8 isu pada daftar ini telah ditangani. Ringkasan detail setiap perbaikan:

### 1. Nominal QRIS salah 100× lipat
- **Status:** ✅ Selesai  
- **Perbaikan:** `PakasirClient` kini mengonversi `amount_cents` ke Rupiah sebelum memanggil API atau membangun checkout URL.  
- **File:** `src/services/pakasir.py`  
- **Catatan:** Log juga menampilkan nilai Rupiah agar audit gateway lebih mudah.

### 2. Pesan expired tidak dibersihkan
- **Status:** ✅ Selesai  
- **Perbaikan:** Job `check_expired_payments_job` menandai payment failed, menghapus pesan invoice lama, mengganti notifikasi admin dengan status dibatalkan, serta mengirim pesan pembatalan baru ke user.  
- **File:** `src/core/tasks.py`, `src/services/payment.py`, `src/services/payment_messages.py`, `src/bot/handlers.py`

### 3. Welcome message & inline button
- **Status:** ✅ Selesai  
- **Perbaikan:** Pesan welcome dirombak sesuai brief (bold, statistik bersih) dengan inline button `ℹ️ INFORMASI` & `📘 Cara Order` + keyboard utama.  
- **File:** `src/bot/messages.py`, `src/bot/handlers.py`, `src/bot/keyboards.py`

### 4. Panel INFORMASI + submenu
- **Status:** ✅ Selesai  
- **Perbaikan:** Panel info menampilkan nama, saldo (format Rupiah), Bank ID, status verifikasi, dan ID Telegram; tombol Settings, Customer Service, dan Last Transaction aktif. User dapat mengubah display name & nomor WhatsApp langsung dari bot.  
- **File:** `src/bot/handlers.py`, `src/services/users.py`, `src/services/order.py`

### 5. Custom template “Cara Order” (teks & gambar)
- **Status:** ✅ Selesai  
- **Perbaikan:** Menu `🛠 Kelola Respon Bot` menambahkan opsi `📘 Edit Cara Order`. Admin bisa mengirim teks saja atau foto + caption. Template tersimpan di custom config disertai placeholder `{nama}` dan `{store_name}`.  
- **File:** `src/bot/admin/admin_menu.py`, `src/bot/handlers.py`, `src/core/custom_config.py`

### 6. Format “Cek Stok” + tombol refresh
- **Status:** ✅ Selesai  
- **Perbaikan:** Pesan stok menampilkan tanggal lokal, penomoran konsisten, dan stok per produk dalam bold. Ditambah tombol `🔄 Refresh` untuk update cepat.  
- **File:** `src/bot/handlers.py`, `src/bot/keyboards.py`

### 7. Penegasan format bold
- **Status:** ✅ Selesai  
- **Perbaikan:** Copy baru (welcome, info panel, stok, notifikasi expired) memakai `<b>...</b>` sesuai guideline dan lebih rapi.  
- **File:** `src/bot/messages.py`, `src/bot/handlers.py`

### 8. Review skenario tambahan & dokumentasi
- **Status:** ✅ Selesai  
- **Perbaikan:** Ditambahkan ledger pesan pembayaran (`src/services/payment_messages.py`), dibersihkan log expired, diuji `compileall src` & `compileall tests`, dan dokumentasi/README/CHANGELOG diperbarui ke v0.5.3.

### Uji yang dijalankan
- `python -m compileall src`
- `python -m compileall tests`

Semua perbaikan telah dipublikasikan pada rilis **0.5.3**.
