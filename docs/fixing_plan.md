# Rencana Perbaikan Masalah - Bot Auto Order

## Status Perbaikan

### ✅ SELESAI - Masalah yang Sudah Diperbaiki

#### 1. ✅ Mismatch Harga QRIS antara Invoice dan Pembayaran
**Masalah:** Total di invoice Rp 30.520 tapi QRIS tagih Rp 31.044 (double fee calculation)

**Penyebab:** Sistem menghitung fee 0.7% + Rp310, lalu menambahkannya ke amount yang dikirim ke Pakasir. Padahal Pakasir juga otomatis menambahkan fee yang sama, sehingga terjadi penghitungan ganda.

**Solusi:**
- ✅ Update `src/core/currency.py`: Tambahkan warning bahwa `calculate_gateway_fee()` hanya untuk display
- ✅ Update `src/services/payment.py`: Kirim hanya `total_cents` ke Pakasir, bukan `payable_cents`
- ✅ Update `src/services/pakasir.py`: Pastikan amount yang dikirim adalah subtotal saja
- ✅ Biarkan Pakasir menambahkan fee secara otomatis di sisi mereka

**File yang Diubah:**
- `src/core/currency.py` - Tambah dokumentasi
- `src/services/payment.py` - Line 186, 235, 264, 294 - kirim `total_cents` bukan `payable_cents`

---

#### 2. ✅ Replace "Pakasir" dengan "Biaya Layanan"
**Masalah:** Kata "Pakasir" muncul di berbagai pesan, harus diganti dengan "Biaya Layanan"

**Solusi:**
- ✅ Update `src/bot/messages.py` - Semua referensi "Pakasir" → "Biaya Layanan"
- ✅ Update `src/bot/handlers.py` - Admin notification

**File yang Diubah:**
- `src/bot/messages.py` - Line 118, 152, 177
- `src/bot/handlers.py` - Line 764

---

#### 3. ✅ Bot Membalas Pesan Acak dengan Error "Sistem Sibuk"
**Masalah:** Bot selalu membalas pesan tidak dikenal dengan error "sistem lagi sibuk nih"

**Solusi:**
- ✅ Remove `generic_error()` call dari `text_router` di handlers.py
- ✅ Biarkan pesan tidak dikenal diabaikan (tidak perlu balasan)
- ✅ Generic error hanya muncul untuk rate limiting atau error sistem nyata

**File yang Diubah:**
- `src/bot/handlers.py` - Line 1980-1982 - Replace dengan `pass`

---

#### 4. ✅ Welcome Message - Tambah Inline Keyboard
**Masalah:** Welcome message tidak memiliki inline keyboard untuk INFORMASI dan Cara Order

**Solusi:**
- ✅ Tambah inline keyboard dengan tombol "📋 INFORMASI" dan "📖 Cara Order"
- ✅ Update format welcome message sesuai requirement
- ✅ Kirim reply keyboard secara terpisah untuk UX lebih baik

**File yang Diubah:**
- `src/bot/messages.py` - Line 21-27 - Simplify welcome text
- `src/bot/handlers.py` - Line 366-391 - Tambah inline keyboard
- `src/bot/handlers.py` - Line 2117, 2124 - Tambah handler untuk `info_bot` dan `info_howto`

---

#### 5. ✅ Database Schema - Product Contents System
**Masalah:** Tidak ada sistem untuk menyimpan "isi produk" (digital product data)

**Solusi:**
- ✅ Buat tabel baru `product_contents` untuk menyimpan data produk digital
- ✅ Tambah kolom: `id`, `product_id`, `content`, `is_used`, `used_by_order_id`, `created_at`, `used_at`
- ✅ Buat index untuk performa: `idx_product_contents_product`, `idx_product_contents_unused`
- ✅ Stok produk akan otomatis sync dengan jumlah content yang belum digunakan

**File yang Diubah:**
- `scripts/schema.sql` - Line 40-47 - Tambah tabel product_contents

---

#### 6. ✅ Product Content Service
**Masalah:** Tidak ada service untuk mengelola product contents

**Solusi:**
- ✅ Buat service baru `src/services/product_content/__init__.py`
- ✅ Fungsi: `add_product_content()`, `get_available_content()`, `mark_content_as_used()`
- ✅ Fungsi: `get_content_count()`, `delete_product_content()`, `list_product_contents()`
- ✅ Fungsi: `get_order_contents()`, `recalculate_all_stock()`
- ✅ Auto-update stok produk berdasarkan jumlah content yang tersedia

**File yang Dibuat:**
- `src/services/product_content/__init__.py` - 329 lines

---

#### 7. ✅ Payment Service - Integrasi Product Content
**Masalah:** Saat pembayaran sukses, sistem hanya mengurangi stok tanpa mengalokasikan content

**Solusi:**
- ✅ Update `mark_payment_completed()` untuk mengalokasikan product content
- ✅ Gunakan `get_available_content()` dan `mark_content_as_used()`
- ✅ Update `sold_count` produk saat pembayaran sukses
- ✅ Stok otomatis update berdasarkan content yang tersisa

**File yang Diubah:**
- `src/services/payment.py` - Line 388-441 - Replace stock deduction dengan content allocation
- `src/services/payment.py` - Line 1-30 - Import product_content service

---

#### 8. ✅ Admin Notification - Status Pembayaran
**Masalah:** Notifikasi admin tidak mencantumkan status pembayaran

**Solusi:**
- ✅ Tambah field "Status: ⏳ Menunggu Pembayaran" di notifikasi order baru
- ✅ Buat fungsi `_notify_admins_payment_success()` untuk notif saat bayar sukses
- ✅ Buat fungsi `_notify_admins_deposit_success()` untuk notif saat deposit sukses
- ✅ Kirim notifikasi lengkap dengan detail customer dan produk

**File yang Diubah:**
- `src/bot/handlers.py` - Line 702 - Tambah status di notifikasi order
- `src/services/payment.py` - Line 548-630 - Tambah fungsi notifikasi payment success
- `src/services/payment.py` - Line 632-691 - Tambah fungsi notifikasi deposit success
- `src/services/payment.py` - Line 462, 742 - Call notifikasi functions

---

#### 9. ✅ Product List - Horizontal Inline Keyboard
**Masalah:** Inline keyboard untuk memilih produk ditampilkan vertikal (1 tombol per baris)

**Solusi:**
- ✅ Update layout menjadi horizontal dengan maksimal 5 tombol per baris
- ✅ Otomatis wrap ke baris baru jika lebih dari 5 produk

**File yang Diubah:**
- `src/bot/handlers.py` - Line 567-579 - Change vertical to horizontal layout

---

### 🔄 SEBAGIAN SELESAI - Perlu Improvement Lebih Lanjut

#### 10. 🔄 Expired Invoice Auto-Delete & Notification
**Status:** Handler sudah ada di `src/core/tasks.py`, tapi perlu verifikasi

**Yang Sudah Ada:**
- ✅ Scheduled job `check_expired_payments_job()` berjalan setiap 60 detik
- ✅ Query payments dengan status 'created'/'waiting' dan expires_at < NOW()
- ✅ Mark payment as failed via `mark_payment_failed()`
- ✅ Send notification ke user
- ✅ Delete/edit payment messages

**Yang Perlu Dicek:**
- ⚠️ Pastikan expires_at disimpan dengan benar dari Pakasir API
- ⚠️ Pastikan timezone konsisten (UTC vs Asia/Jakarta)
- ⚠️ Test manual untuk memastikan pesan dihapus setelah 5 menit

**File Terkait:**
- `src/core/tasks.py` - Line 55-305
- `src/services/payment.py` - Line 196-221 (save expires_at)

---

#### 11. 🔄 Timezone dan Waktu Spesifik
**Status:** Sudah ada support timezone, tapi perlu verifikasi format

**Yang Sudah Ada:**
- ✅ Setting `BOT_TIMEZONE` di config (default: Asia/Jakarta)
- ✅ Fungsi `_format_local_timestamp()` untuk konversi timezone

**Yang Perlu Diperbaiki:**
- ⚠️ Pastikan "expires_in" menampilkan waktu spesifik, bukan hanya "5 Menit"
- ⚠️ Format waktu expired yang lebih user-friendly: "06/11/2025 13:26" (created + 5 menit)
- ⚠️ Konsistensi timezone di semua timestamp

**File Terkait:**
- `src/bot/handlers.py` - Line 383-408, 1193-1200, 2960-2968
- `src/bot/messages.py` - Line 137-162, 164-183

---

### ⏳ PENDING - Belum Dikerjakan (Perlu Implementasi Lebih Lanjut)

#### 12. ⏳ Admin Product Management - Add/Edit Stock via Content
**Masalah:** Admin bisa set stok manual saat tambah produk, tapi stok harus based on content

**Requirement:**
- [ ] Saat tambah produk baru, langkah 5/6 adalah "Kirim Isi Produk" (WAJIB)
- [ ] Format isi produk: data yang diterima customer setelah bayar (email, password, code, dll)
- [ ] Langkah 6/6 baru deskripsi produk (opsional)
- [ ] Hilangkan input stok manual dari flow tambah produk
- [ ] Di "Kelola Produk", tambah menu "➕ Tambah Stok" dan "📝 Edit Stok"
- [ ] Admin harus input content satu per satu untuk menambah stok
- [ ] Stok = COUNT(*) FROM product_contents WHERE is_used = FALSE

**Action Items:**
- [ ] Update `admin_state.py` - Tambah state untuk input product content
- [ ] Update `admin_actions.py` - Modify `handle_add_product_input()` untuk handle content
- [ ] Tambah fungsi `handle_add_product_content()` untuk menerima content
- [ ] Tambah menu "Kelola Stok Produk" di `admin_menu.py`
- [ ] Buat handler untuk "Tambah Stok" dan "Edit Stok" via content input

**File yang Perlu Diubah:**
- `src/bot/admin/admin_state.py`
- `src/bot/admin/admin_actions.py`
- `src/bot/admin/admin_menu.py`

---

#### 13. ⏳ Payment Success - Send Product Content to Customer
**Masalah:** Saat pembayaran sukses, customer harus menerima "isi produk" dan "SNK"

**Requirement:**
- [ ] Setelah payment completed, ambil content dari `product_contents` via order
- [ ] Format pesan: "🎉 Pembayaran Berhasil!\n\n📦 Detail Produk:\n[PRODUCT_CONTENT]\n\n📜 S&K:\n[SNK]"
- [ ] Kirim ke customer via Telegram
- [ ] Log delivery di database

**Action Items:**
- [ ] Update notification handler di payment service
- [ ] Query `get_order_contents(order_id)` untuk ambil content
- [ ] Format dan kirim ke customer
- [ ] Include SNK jika ada

**File yang Perlu Diubah:**
- `src/services/payment.py` - Function di mark_payment_completed
- `src/bot/messages.py` - Template untuk product delivery

---

#### 14. ⏳ Deposit QRIS - Sama dengan Payment
**Masalah:** Masalah di deposit sama dengan payment (mismatch, expired, dll)

**Status:** Sudah diperbaiki di payment service, tapi perlu testing deposit flow

**Action Items:**
- [ ] Test deposit QRIS end-to-end
- [ ] Verifikasi fee calculation sudah benar
- [ ] Verifikasi expired handling sudah benar
- [ ] Verifikasi admin notification deposit success

---

## Testing Checklist

### Critical Path Testing
- [ ] **Payment Flow (QRIS)**
  - [ ] Create order → Check invoice amount matches QRIS amount
  - [ ] Scan QRIS → Pay → Verify customer receives product content
  - [ ] Verify admin receives notification (pending + success)
  - [ ] Verify stock decrements correctly based on content
  
- [ ] **Deposit Flow (QRIS)**
  - [ ] Create deposit → Check invoice amount matches QRIS amount
  - [ ] Scan QRIS → Pay → Verify balance increases
  - [ ] Verify admin receives notification (pending + success)
  
- [ ] **Expired Invoice**
  - [ ] Create order → Wait 5 minutes
  - [ ] Verify invoice message is deleted
  - [ ] Verify user receives cancellation notification
  - [ ] Verify stock is restored
  
- [ ] **Welcome Message**
  - [ ] Send /start → Verify inline keyboard appears
  - [ ] Click "📋 INFORMASI" → Verify info displayed
  - [ ] Click "📖 Cara Order" → Verify howto displayed
  
- [ ] **Product List**
  - [ ] Open product list → Verify buttons are horizontal
  - [ ] Verify max 5 buttons per row

### Product Content System Testing
- [ ] **Add Product Content**
  - [ ] Add content via admin menu
  - [ ] Verify stock auto-increments
  - [ ] Verify content is marked as unused
  
- [ ] **Purchase with Content**
  - [ ] Buy product → Pay → Verify content delivered
  - [ ] Verify content marked as used
  - [ ] Verify stock decrements
  
- [ ] **Stock Management**
  - [ ] Delete unused content → Verify stock decrements
  - [ ] Recalculate all stock → Verify consistency

---

## Migration Steps (For Production)

### 1. Database Migration
```sql
-- Run this on production database
-- File: scripts/schema.sql (lines 40-47, 130-132)

CREATE TABLE IF NOT EXISTS product_contents (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    is_used BOOLEAN DEFAULT FALSE,
    used_by_order_id UUID REFERENCES orders(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    used_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_product_contents_product ON product_contents(product_id);
CREATE INDEX IF NOT EXISTS idx_product_contents_unused ON product_contents(product_id, is_used) WHERE is_used = FALSE;
```

### 2. Migrate Existing Products
```python
# Script untuk migrate existing products ke content-based stock
# Untuk setiap produk yang ada, admin harus input content secara manual
# Atau bisa buat dummy content untuk transisi
```

### 3. Deploy Code Changes
- [ ] Build new Docker image
- [ ] Update deployment
- [ ] Monitor logs for errors
- [ ] Test payment flow immediately

### 4. Notify Admins
- [ ] Inform about new product content system
- [ ] Train admins on adding product content
- [ ] Update documentation

---

## Known Issues & Considerations

### 1. Product Stock Transition
**Issue:** Existing products memiliki stok tapi tidak ada content di database

**Options:**
- A. Admin harus input content untuk semua existing stock (manual, akurat)
- B. Generate dummy content untuk existing stock (quick, tapi tidak ada real data)
- C. Set semua stock = 0 dan admin tambah content baru (safe, clean slate)

**Recommendation:** Option C - Start fresh dengan content-based stock

### 2. Content Format
**Issue:** Tidak ada validasi atau format standar untuk product content

**Recommendation:**
- Content bisa berupa text bebas
- Admin yang tanggung jawab ensure format konsisten
- Bisa tambah template di masa depan jika perlu

### 3. Partial Stock Delivery
**Issue:** Jika customer pesan 5x tapi hanya ada 3 content

**Current Behavior:** 
- Mark 3 content sebagai used
- Log error
- Customer tetap dapat yang ada

**Recommendation:**
- Tambah validasi di checkout: cek stock availability sebelum create order
- Prevent checkout jika stock tidak cukup

---

## Next Steps Priority

### High Priority (Do First)
1. ✅ Fix fee calculation (SELESAI)
2. ✅ Fix welcome message inline keyboard (SELESAI)
3. ✅ Remove generic error dari text router (SELESAI)
4. ✅ Add product contents schema (SELESAI)
5. ⏳ Test payment flow end-to-end
6. ⏳ Implement product content delivery to customer (#13)

### Medium Priority (Do Next)
7. ⏳ Update admin product management for content-based stock (#12)
8. ⏳ Test and verify expired invoice handling (#10)
9. ⏳ Improve timezone display (#11)
10. ⏳ Test deposit flow thoroughly (#14)

### Low Priority (Nice to Have)
11. Add content format templates
12. Add bulk content upload feature
13. Add content preview for admin
14. Add statistics for content usage

---

## Files Modified Summary

### Core Services
- ✅ `src/core/currency.py` - Fee calculation documentation
- ✅ `src/services/payment.py` - Fee fix, content allocation, admin notifications
- ⏳ `src/services/pakasir.py` - No changes needed (already correct)
- ✅ `src/services/product_content/__init__.py` - NEW FILE

### Bot Handlers
- ✅ `src/bot/handlers.py` - Welcome keyboard, generic error, product list layout, admin notif
- ✅ `src/bot/messages.py` - Replace "Pakasir", update welcome message
- ⏳ `src/bot/admin/admin_actions.py` - PENDING: Update for content-based products
- ⏳ `src/bot/admin/admin_menu.py` - PENDING: Add stock management menu
- ⏳ `src/bot/admin/admin_state.py` - PENDING: Add content input states

### Database
- ✅ `scripts/schema.sql` - Add product_contents table

### Documentation
- ✅ `docs/fixing_plan.md` - THIS FILE (updated)

---

## Conclusion

**Progress:** 9/14 masalah selesai (64%)

**Status Kritis yang Sudah Fixed:**
- ✅ Fee calculation double (SOLVED)
- ✅ Generic error spam (SOLVED)
- ✅ Welcome message no keyboard (SOLVED)
- ✅ Admin notification incomplete (SOLVED)

**Next Action:** 
1. Test payment flow untuk verify fee calculation benar
2. Implement product content delivery ke customer
3. Update admin product management untuk content-based stock

**Estimated Time to Complete:** 4-6 jam untuk remaining items

---

*Last Updated: 2025-01-XX*
*Version: v0.6.0-fixing*