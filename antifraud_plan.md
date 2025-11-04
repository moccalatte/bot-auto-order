# Antifraud & Complaint Mitigation Plan – Bot Auto Order

## Peran & Batasan Akses
- **Owner**: Pemilik bot auto order, menyewakan bot ke seller/admin. Owner punya akses penuh ke audit, log, dan override status/order. Tidak punya akses ke data customer kecuali lewat audit/log.
- **Seller (Admin)**: Penyewa bot, mengelola toko dan transaksi via bot Telegram. Tidak punya akses ke codebase/server, hanya bisa kelola produk, order, user, dan kustomisasi bot via menu admin Telegram.
- **Buyer (Customer)**: Pembeli produk digital, berinteraksi dengan bot untuk order, pembayaran, dan komplain.

---

## Tujuan
Menjamin keamanan, keadilan, dan perlindungan bagi owner, admin/seller, dan customer dari potensi fraud, keisengan, atau komplain palsu terkait transaksi dan pengiriman produk digital.

---

## 1. Potensi Fraud, Keisengan, & Kerugian

### A. Buyer (Customer)
- **Merugikan Seller/Admin:** Mengaku produk tidak diterima padahal sudah dikirim bot, mengaku bot error padahal transaksi sukses, mengaku pembayaran gagal padahal sudah sukses, mengaku sudah transfer padahal belum, mengaku produk rusak/palsu untuk refund/kompensasi, menggunakan identitas palsu/multiple akun untuk promo/bonus.
- **Siapa yang handle:** Seller/admin wajib cek log pengiriman produk dan status pembayaran. Owner bisa audit jika dispute.

### B. Seller (Admin)
- **Merugikan Buyer/Customer:** Tidak mengirim produk setelah pembayaran sukses, mengubah status order tanpa alasan jelas, menolak refund tanpa alasan valid, menyalahgunakan akses admin untuk manipulasi data.
- **Merugikan Owner:** Menghapus/memodifikasi riwayat transaksi, menyalahgunakan fitur bot untuk fraud, manipulasi data order/user.
- **Siapa yang handle:** Owner punya hak audit penuh, override status, dan cabut akses admin jika ditemukan fraud.

### C. Owner
- **Potensi kerugian:** Jika seller/admin melakukan fraud, owner bisa kehilangan reputasi dan kepercayaan customer. Jika sistem bot error atau log/audit tidak berjalan, owner tidak bisa membuktikan dispute.
- **Siapa yang handle:** Owner wajib audit log, override status, dan update antifraud plan secara berkala.

---

## 2. Strategi Antisipasi & Perlindungan

### A. Logging & Audit Trail
- **Semua transaksi, pengiriman produk, refund, dan perubahan status order dicatat di log (timestamp, user_id, order_id, status, detail).**
- **Log tidak bisa dihapus/diubah oleh seller/admin. Owner punya akses audit penuh.**
- **Jika terjadi dispute, owner wajib cek log dan audit trail sebelum ambil keputusan.**

### B. Notifikasi & Konfirmasi
- **Bot mengirim notifikasi ke owner dan seller/admin setiap transaksi sukses/gagal, pengiriman produk, dan refund.**
- **Bot mengirim konfirmasi ke customer saat produk dikirim (waktu, order_id, produk, dsb).**
- **Jika terjadi error, bot otomatis mengirim log error ke owner dan seller/admin.**

### C. Idempotensi & Validasi
- **Pengiriman produk hanya dilakukan jika status pembayaran sudah “completed” dan diverifikasi via webhook.**
- **Setiap order_id dan transaksi diverifikasi idempotensi agar tidak terjadi double delivery.**
- **Validasi signature webhook (PAKASIR_WEBHOOK_SECRET) untuk mencegah spoofing/fraud.**

### D. Bukti Pengiriman Produk
- **Bot menyimpan bukti pengiriman produk (log, timestamp, order_id, user_id, isi produk).**
- **Owner dan seller/admin dapat mengakses riwayat pengiriman produk untuk investigasi komplain.**
- **Jika customer komplain, seller/admin handle dulu, owner audit jika dispute berlanjut.**

### E. Rate Limit & Anti-Spam
- **Bot menerapkan rate limit dan anti-spam pada semua aksi customer dan seller/admin.**
- **Jika terdeteksi spam/aksi mencurigakan, bot mengirim peringatan dan log ke seller/admin.**

### F. Verifikasi Identitas
- **Setiap transaksi dan pengiriman produk dikaitkan dengan Telegram ID dan username customer.**
- **Bot menolak transaksi dari akun anonim atau yang terdeteksi sebagai spam/multiple akun.**

### G. Sistem Refund & Dispute
- **Refund hanya diproses jika log pembayaran dan pengiriman produk diverifikasi owner dan seller/admin.**
- **Jika terjadi dispute, seller/admin handle dulu, owner wajib cek log dan bukti pengiriman sebelum keputusan akhir.**
- **Bot menyediakan fitur upload bukti (screenshot, chat, dsb) untuk dispute manual.**

### H. Proteksi Owner & Seller
- **Owner dapat override status order dan refund jika ditemukan fraud/keisengan seller/admin/customer.**
- **Seller/admin tidak bisa menghapus/memodifikasi log transaksi dan pengiriman produk.**
- **Bot otomatis rollback ke status default jika terjadi error konfigurasi atau fraud terdeteksi.**

---

## 3. Mitigasi & Tindakan Lanjutan

- **Fraud/keisengan customer (merugikan seller/admin):**
  - Seller/admin handle komplain, cek log pengiriman dan pembayaran.
  - Jika terbukti fraud, seller/admin blokir akun, blacklist Telegram ID, dan laporkan ke owner.
  - Owner audit log dan bisa override keputusan seller/admin.

- **Fraud/keisengan seller/admin (merugikan customer/owner):**
  - Owner audit seluruh transaksi dan log terkait.
  - Owner cabut akses admin, informasikan ke seluruh seller/admin lain.
  - Seller/admin tidak bisa hapus log, semua tindakan tercatat di audit trail.

- **Fraud/keisengan yang merugikan owner:**
  - Owner wajib audit log, update antifraud plan, dan lakukan investigasi.
  - Jika sistem bot error/log tidak berjalan, owner wajib perbaiki dan informasikan ke seller/admin.

- **Dispute/komplain produk:**
  - Seller/admin handle komplain customer terlebih dahulu.
  - Jika dispute berlanjut, owner audit log, bukti pengiriman, dan status pembayaran.
  - Keputusan refund/kompensasi hanya diambil berdasarkan data log dan audit owner.

- **Update antifraud plan secara berkala** sesuai pola keisengan/fraud terbaru.

---

## 4. Checklist Perlindungan

- [x] Logging transaksi, pengiriman produk, refund, dan perubahan status order.
- [x] Audit trail tidak bisa dihapus/diubah seller/admin.
- [x] Notifikasi ke owner dan seller/admin untuk semua aksi penting.
- [x] Validasi pembayaran via webhook dan signature.
- [x] Bukti pengiriman produk tersimpan dan bisa diakses owner dan seller/admin.
- [x] Rate limit dan anti-spam aktif.
- [x] Verifikasi identitas customer.
- [x] Sistem refund/dispute berbasis log dan audit, seller/admin handle dulu, owner audit akhir.
- [x] Proteksi override untuk owner.
- [x] Update antifraud plan secara berkala.

---

## 5. Catatan

- **Bot wajib menjaga keadilan dan keamanan semua pihak (owner, seller/admin, customer).**
- **Setiap komplain/fraud harus diinvestigasi berbasis data log dan audit, bukan asumsi.**
- **Owner adalah otoritas tertinggi dalam dispute dan antifraud, seller/admin handle komplain awal, owner audit dan override jika perlu.**
- **Seller/admin hanya bisa kelola bot via Telegram, tidak punya akses codebase/server.**
- **Owner wajib update antifraud plan dan audit log secara berkala.**
