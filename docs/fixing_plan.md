## Rencana Perbaikan – Status 6 Nov 2025

- [x] **1. Welcome Message** – `/start` kini mengirim satu pesan HTML dengan keyboard utama; teks petunjuk keyboard di-embed dalam welcome template (`src/bot/messages.py`, `src/bot/handlers.py`, `src/bot/keyboards.py`).
- [x] **2. Format Tanggal Stok** – Pesan `🏷 Cek Stok` memakai format `dd/mm/YYYY HH:MM` dengan timezone `Asia/Jakarta` (`_build_stock_overview_message`).
- [x] **3. Total Dibayar QRIS** – Invoice & prompt pembayaran menampilkan subtotal, fee (0,7% + Rp310), dan total dibayar; PaymentService mengirim nominal akhir ke Pakasir (`src/services/payment.py`, `src/bot/messages.py`, `src/bot/handlers.py`).
- [x] **4. Cleanup Invoice Expired** – `check_expired_payments_job` menghapus/ mengedit pesan user & admin dengan fallback, mengirim pesan pembatalan baru, dan menghapus log (`src/core/tasks.py`).
- [x] **5. Deposit QRIS** – Alur deposit otomatis aktif (minimal Rp10.000) dengan perhitungan fee, pencatatan `deposits`, notifikasi admin, dan cleanup kadaluarsa (`src/services/deposit.py`, `src/services/payment.py`, `src/bot/handlers.py`, `src/bot/keyboards.py`, `docs/*`).
- [x] **6. Checkout Guard** – Keranjang kosong menampilkan peringatan + tombol kembali, tombol `💳 Lanjut ke Pembayaran` disembunyikan, dan aksi `cart:pay` menolak keranjang kosong.
- [x] **7. Review & Testing** – Manual test welcome/stock/cart/payment/deposit; unit-test baru (`python -m unittest discover`) untuk fee, keyboard, dan template. Beberapa test diskip karena dependency eksternal tidak tersedia di sandbox.
- [x] **8. Dokumentasi** – Semua dokumen `docs/00_context.md` sampai `docs/10_roadmap_critical.md`, `CHANGELOG.md`, `QUICK_REFERENCE.md`, `TESTING_CHECKLIST.md`, `README.md`, dan berkas ini diperbarui dengan status rilis 0.5.4.

### Catatan Tambahan
- Scheduler `check_expired_payments_job` sekarang menangani order *dan* deposit.
- Helper baru `calculate_gateway_fee` dijadikan referensi tunggal untuk penambahan biaya Pakasir.
- Ada fallback log editing ketika bot tidak bisa menghapus pesan (misal out-of-window).
