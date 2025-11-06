## rencana perbaikan masalah
ada 6 masalah disini

### ✅ 1. Welcome Message & Inline Keyboard - **FIXED**
**Status:** COMPLETED ✅

**Masalah:**
- Pesan welcome tidak memiliki inline keyboard "cek stok" dan "semua produk"
- Ada pesan terpisah "📱 Aksi Cepat:" yang tidak diinginkan

**Solusi Implemented:**
- Welcome message sekarang langsung memiliki inline keyboard dengan tombol "🏷 Cek Stok" dan "🛍 Semua Produk"
- Pesan "📱 Aksi Cepat:" telah dihapus sepenuhnya
- Menu navigation disediakan melalui pesan terpisah yang minimal

**File Modified:**
- `src/bot/handlers.py` - function `_send_welcome_message()`

---

### ✅ 2. Transfer Manual Contact Info - **FIXED**
**Status:** COMPLETED ✅

**Masalah:**
- Menampilkan `@user_id_341404536` yang merupakan owner ID, bukan admin ID
- Format tidak proper (bukan hyperlink)

**Solusi Implemented:**
- Sekarang menggunakan `telegram_admin_ids` bukan `telegram_owner_ids`
- Format hyperlink proper: `<a href="tg://user?id={admin_id}">admin</a>`
- Fallback ke owner jika admin tidak dikonfigurasi

**File Modified:**
- `src/bot/handlers.py` - callback handler untuk `deposit:manual`

---

### ✅ 3. Payment QR & Expiration Handling - **FIXED**
**Status:** COMPLETED ✅

**Masalah:**
- QR code mungkin tidak valid (issue dengan Pakasir API)
- Urutan pesan berantakan (notify admin dulu, baru kirim invoice ke user)
- Tidak ada auto-cancel setelah 5 menit expired
- Tidak ada notifikasi expired ke user

**Solusi Implemented:**

#### A. Payment Flow Improvement:
- Loading message sekarang di-edit (tidak bikin pesan baru)
- Urutan diperbaiki: kirim invoice ke user DULU, baru notify admin
- Cart di-clear otomatis setelah pembayaran dibuat
- QR code tetap menggunakan `payment_number` dari Pakasir response

#### B. Expired Payment Monitoring:
- Tambah kolom `expires_at` ke database payments (sudah ada di schema)
- Save `expired_at` dari Pakasir response ke database
- Implement scheduled job `check_expired_payments_job` yang jalan setiap 1 menit
- Job akan:
  1. Query semua payment dengan status `created`/`waiting` yang sudah expired
  2. Mark payment sebagai failed
  3. Kirim notifikasi ke user dengan format lengkap
  4. Restock produk otomatis

#### C. User Notification:
Format notifikasi expired:
```
⏰ Pembayaran Kedaluwarsa

💳 ID Transaksi: tg5473468582-a916f77a

⚠️ Maaf, waktu pembayaran sudah habis.
Pesanan kamu telah dibatalkan secara otomatis.

🔄 Silakan buat pesanan baru jika masih ingin membeli.
💬 Hubungi admin jika ada pertanyaan.
```

**Files Modified:**
- `src/services/payment.py` - save expires_at dari Pakasir
- `src/core/tasks.py` - add check_expired_payments_job
- `src/core/scheduler.py` - register job
- `src/bot/handlers.py` - fix payment flow order

---

### ✅ 4. Payment Mechanism Review - **VERIFIED**
**Status:** COMPLETED ✅

**Review Findings:**
- ✅ Menggunakan endpoint `/api/transactioncreate/qris` dengan benar
- ✅ Payment number untuk QR generation sudah proper
- ✅ Webhook handling sudah implement status `expired`, `failed`, `cancelled`
- ✅ QRIS-only mode aktif (`qris_only=1` di URL)
- ✅ Expires_at field dari API sekarang disimpan ke database

**Pakasir Integration Checklist:**
- [x] Create transaction endpoint
- [x] QR code generation via `payment_number`
- [x] Webhook handling (completed/failed/expired)
- [x] Expires_at tracking
- [x] Auto-cancel expired payments
- [x] User notification system

---

### 🔄 5. Testing All Flows - **IN PROGRESS**
**Status:** REQUIRES MANUAL TESTING ⚠️

**Areas to Test:**

#### ReplyKeyboardMarkup Menus:
- [ ] Customer main menu (📋 List Produk, 🛍 Semua Produk, 🏷 Cek Stok, 💰 Deposit)
- [ ] Admin main menu navigation
- [ ] Admin settings submenus

#### InlineKeyboard Flows:
- [ ] Welcome inline keyboard (Cek Stok, Semua Produk)
- [ ] Product list pagination (Previous/Next)
- [ ] Product detail (add to cart, quantity controls)
- [ ] Cart actions (checkout, coupon, cancel)
- [ ] Payment method selection (QRIS, Balance, Cancel)
- [ ] Invoice actions (Checkout URL, Cancel)
- [ ] Admin actions (add/edit/delete product, voucher, broadcast, etc.)
- [ ] Cancel buttons across all admin flows

#### Payment Flow End-to-End:
- [ ] Browse product → Add to cart → Checkout → QRIS payment
- [ ] Payment loading indicator
- [ ] QR code display
- [ ] Expired payment notification (wait 5 minutes)
- [ ] Webhook callback (use Pakasir simulation)

#### Admin Flows:
- [ ] Add product wizard (5 steps)
- [ ] Edit product flow
- [ ] Delete product with confirmation
- [ ] Generate voucher
- [ ] Block/unblock user
- [ ] Broadcast message
- [ ] Calculator menu

**Testing Script:** See `docs/TESTING_CHECKLIST.md` for detailed test scenarios

---

### 📝 6. Documentation Update - **IN PROGRESS**
**Status:** PARTIALLY COMPLETED ⚠️

**Updated Files:**
- [x] `docs/fixing_plan.md` - This file (current status update)
- [ ] `docs/00_context.md` - Need to add v0.5.0 context
- [ ] `docs/01_dev_protocol.md` - Update with new patterns
- [ ] `docs/02_prd.md` - Add payment expiration feature
- [ ] `docs/03_architecture_plan.md` - Document scheduled jobs
- [ ] `docs/04_dev_tasks.md` - Mark tasks complete
- [ ] `docs/05_security_policy.md` - Review
- [ ] `docs/06_risk_audit.md` - Add payment risks
- [ ] `docs/07_quality_review.md` - Update metrics
- [ ] `docs/08_release_notes.md` - Add v0.5.0 entry
- [ ] `docs/09_maintenance_plan.md` - Add job monitoring
- [ ] `docs/10_roadmap_critical.md` - Update priorities
- [ ] `docs/CHANGELOG.md` - Add v0.5.0 changelog
- [ ] `README.md` - Bump version to v0.5.0

**TODO:** Complete documentation sweep after manual testing confirms all fixes work correctly.

---

## Summary

**Fixes Completed:** 4 out of 6
- ✅ Welcome message inline keyboard
- ✅ Transfer manual admin contact
- ✅ Payment flow & expired handling
- ✅ Payment mechanism review
- 🔄 Manual testing required
- 🔄 Documentation in progress

**Next Steps:**
1. Run manual testing checklist (see issue #5)
2. Complete documentation updates (issue #6)
3. Deploy to staging for QA
4. Production deployment after sign-off

**Version:** v0.5.0-rc (Release Candidate)
**Date:** 2025-01-XX
**Reviewer:** Senior Level Agent (IQ 150 😉)
