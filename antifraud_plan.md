# Rencana Anti-Fraud (Owner ↔ Seller)

**Konteks Singkat**  
Owner menyewakan dan mengoperasikan instance bot pada VPS sendiri. Seller membawa token BotFather serta akun Pakasir mereka, sementara customer berinteraksi langsung dengan bot. Tanggung jawab owner adalah memastikan semua transaksi otomatis lewat payment gateway berjalan aman, anti-komplain, dan mempunyai jejak log yang rapi untuk membela diri jika terjadi sengketa.

---

## Risiko Kecurangan yang Perlu Dijaga

1. **Validitas Transaksi Gateway (Checkout & Deposit Otomatis)**  
   - *Skenario*: seller atau customer menuduh pembayaran gateway gagal padahal sukses (atau sebaliknya).  
   - *Mitigasi sistem*: Payment service kini mencocokkan nominal order vs payload gateway, menggunakan locking `FOR UPDATE`, dan mengabaikan webhook duplikat. Stok berkurang dan direstor otomatis, sehingga tidak ada celah stok negatif. Semua webhook dicatat di log `logs/bot-auto-order/<tanggal>.log`.  
   - *Kontrol owner*: simpan log harian webhook & pembayaran, serta bandingkan dengan laporan Pakasir seller bila muncul komplain.

2. **Pencatatan Deposit Manual (Fallback)**  
   - *Skenario*: seller menerima deposit di luar gateway dan meminta owner mengesahkan order.  
   - *Mitigasi sistem*: status “paid” tanpa pembayaran gateway akan ditolak kecuali admin menambahkan catatan. Catatan tersebut tersimpan di `order_manual_verifications`, jadi owner punya bukti siapa yang meminta verifikasi manual.  
   - *Kontrol owner*: jika catatan manual muncul, minta seller mengirim bukti transfer sebelum melakukan override. Ini mencegah tuduhan bahwa owner menahan dana.

3. **Penyalahgunaan Akses Admin**  
   - *Skenario*: seller memberikan akses admin ke pihak lain yang kemudian membuat perubahan merugikan (voucher ekstrem, blokir customer, ubah status order).  
   - *Mitigasi sistem*: setiap aksi admin direkam (ID Telegram, waktu, nilai perubahan).  
   - *Kontrol owner*: minta seller menyerahkan daftar admin yang sah, audit log ketika ada perubahan mencurigakan, dan jadikan log sebagai bukti jika perlu menegur atau memutus kontrak.


> Preferensi operasional seller (mis. harga produk, promo pribadi) tidak dianggap risiko fatal selama log tersedia. Owner cukup menunjukkan bukti dari log ketika terjadi komplain.

---

## Checklist Monitoring Owner
1. **Harian**: periksa log webhook (status transaksi) dan catatan manual baru.  
2. **Mingguan**: tinjau ringkasan restock (indikasi pembayaran gagal) dan voucher yang dibuat/di-nonaktifkan.  
3. **Saat Sengketa**: gunakan log (webhook, order manual, voucher) sebagai bukti sebelum memutuskan kompensasi atau penalti.

---

## Backlog Teknis (Opsional)
- Notifikasi otomatis (Telegram/email) kepada owner ketika ada catatan manual baru atau voucher di atas ambang diskon.  
- Cron job yang menghasilkan laporan harian berisi transaksi gateway sukses/gagal, restock, dan voucher terbaru.  
- Rekonsiliasi otomatis catatan manual dengan laporan Pakasir seller (jika akses API tersedia).

Dengan fokus pada tiga area di atas dan kebiasaan meninjau log, owner dapat menjaga kepercayaan seller–customer sekaligus memiliki bukti kuat apabila tuduhan kecurangan muncul.
