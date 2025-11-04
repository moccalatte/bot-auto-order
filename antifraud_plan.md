# Rencana Anti-Fraud & Pembatasan Fitur

## Risiko Utama
1. **Manipulasi status order & saldo**  
   Admin dapat mengubah status order menjadi “sukses” tanpa pembayaran sah karena tidak ada verifikasi silang ke gateway.
2. **Penyalahgunaan template pesan**  
   Custom template bisa digunakan untuk membuat pesan palsu (“pembayaran diterima”) yang menipu customer/owner.
3. **Voucher diskon tak terbatas**  
   Admin bisa membuat voucher 100% dan membagikannya ke pihak sendiri tanpa batasan atau audit.
4. **Blokir/unblokir user sewenang-wenang**  
   Tidak ada catatan alasan; bisa menimbulkan konflik dan dugaan diskriminasi.
5. **Upload media produk**  
   Gambar dapat diganti dengan konten palsu/berbahaya, tidak ada mekanisme moderasi.
6. **Replay pembayaran (QR lama)**  
   Customer bisa mencoba memakai ulang QR/invoice lama bila tidak dicek statusnya.

## Rencana Mitigasi
- **Verifikasi Status Order**
  - Simpan hash/invoice_id dan cek status ke gateway sebelum mengubah order jadi “paid”.
  - Tambahkan log yang mencatat admin id, order id, dan bukti verifikasi.
- **Pembekuan Template Kritis**
  - Nonaktifkan pengeditan template langsung dari menu admin. Perubahan hanya via owner.
  - Tetap sediakan menu preview agar admin tahu pesan aktif.
- **Hapus Manajemen Voucher**
  - Hilangkan opsi pembuatan/penghapusan voucher dari menu admin untuk menghindari diskon liar.
  - Jika perlu voucher, buat mekanisme permintaan khusus via owner.
- **Catatan Aksi Admin**
  - Setiap blokir/unblokir wajib mencatat alasan dan timestamp di audit log (direncanakan implementasi berikutnya).
- **Hapus Upload Gambar Produk**
  - Menutup celah penyisipan konten berbahaya serta menyederhanakan approval katalog.
- **Validasi Pembayaran**
  - Saat webhook diterima, pastikan order_id + amount cocok sebelum update status.
  - Arsipkan respons gateway untuk audit.
- **Notifikasi Owner**
  - Rencanakan broadcast ke owner setiap ada perubahan sensitif (status order, blokir, dsb.) untuk early warning.

## Tindakan Langsung (Sprint Ini)
1. Hapus fitur upload gambar produk dari Admin Settings.
2. Hapus seluruh menu Kelola Voucher.
3. Batasi Kelola Respon Bot menjadi hanya **preview** (tanpa edit).
4. Sesuaikan dokumentasi (README & frontend.md) agar mencerminkan fitur baru.
5. Tambahkan plan audit ini ke backlog untuk eksekusi bertahap.
