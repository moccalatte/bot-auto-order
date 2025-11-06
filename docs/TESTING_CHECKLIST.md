# 🧪 Testing & Deployment Checklist – Bot Auto Order Telegram

**Version:** 0.5.0  
**Last Updated:** 2025-01-XX  
**Purpose:** Comprehensive checklist untuk memastikan semua features berfungsi dengan baik sebelum production deployment.

---

## 🆕 Version 0.5.0 Specific Tests

### Critical Fix Verification

#### Test V5.1: Welcome Message Inline Keyboard
**Priority:** HIGH  
**Test Steps:**
1. Send `/start` to bot as customer
2. Verify welcome message includes inline keyboard with:
   - "🏷 Cek Stok" button
   - "🛍 Semua Produk" button
3. Verify NO separate message with "📱 Aksi Cepat:"
4. Click "🏷 Cek Stok" → should show product list
5. Click "🛍 Semua Produk" → should show all products

**Expected Result:**
- ✅ Welcome message has inline keyboard integrated
- ✅ No "📱 Aksi Cepat:" message appears
- ✅ Buttons work correctly

**Rollback If:** Welcome message broken, inline keyboard missing, or extra messages appear

---

#### Test V5.2: Transfer Manual Admin Contact
**Priority:** HIGH  
**Test Steps:**
1. Navigate to: 💰 Deposit → Transfer Manual
2. Verify message shows admin contact as clickable hyperlink
3. Click the admin hyperlink
4. Verify it opens Telegram chat with correct admin user
5. Verify format is NOT `@user_id_{number}`

**Expected Result:**
- ✅ Admin contact is HTML hyperlink: `<a href="tg://user?id={admin_id}">admin</a>`
- ✅ Clicking opens correct admin chat
- ✅ Uses telegram_admin_ids (not owner_ids)

**Rollback If:** Wrong user shown, not clickable, or shows @user_id format

---

#### Test V5.3: Payment Flow Message Order
**Priority:** HIGH  
**Test Steps:**
1. Add product to cart
2. Proceed to checkout → Select QRIS
3. Observe message sequence:
   - Loading message appears
   - Loading message is edited/deleted (not duplicate)
   - Invoice with QR code sent to user FIRST
   - Admin receives order notification AFTER
4. Verify invoice HTML formatting (bold/italic) renders correctly
5. Verify cart is automatically cleared

**Expected Result:**
- ✅ No duplicate loading messages
- ✅ Invoice to user first, admin notification second
- ✅ QR code displays with proper formatting
- ✅ Cart cleared automatically

**Rollback If:** Message order wrong, duplicate messages, or HTML not rendering

---

#### Test V5.4: Payment Expiration Monitoring
**Priority:** CRITICAL  
**Test Steps:**
1. Create a QRIS payment (don't pay)
2. Check database: `SELECT gateway_order_id, expires_at FROM payments WHERE status='created';`
3. Verify `expires_at` is populated (not NULL)
4. Wait 5-6 minutes (or manually update expires_at to past time in DB)
5. Monitor logs: `grep "expired_payments" logs/telegram-bot/*.log`
6. Verify user receives expiration notification:
   - "⏰ Pembayaran Kedaluwarsa"
   - Transaction ID shown
   - Cancellation message
   - Next steps guidance
7. Check database: payment status changed to 'failed'
8. Check product stock: restored to original quantity

**Expected Result:**
- ✅ expires_at saved from Pakasir response
- ✅ Scheduled job runs every ~60 seconds
- ✅ User notified when payment expires
- ✅ Payment marked as failed
- ✅ Product restocked

**Rollback If:** No notification sent, job not running, or stock not restored

---

#### Test V5.5: Scheduled Job Health
**Priority:** MEDIUM  
**Test Steps:**
1. Bot running for at least 5 minutes
2. Check logs: `grep "check_expired_payments" logs/telegram-bot/*.log | tail -20`
3. Verify job executions roughly every 60 seconds
4. Verify no errors or exceptions in job
5. Check job registration at startup: `grep "check_expired_payments" logs/*`

**Expected Result:**
- ✅ Job registered at bot startup
- ✅ Job runs every 60±5 seconds
- ✅ No errors in job execution
- ✅ Handles empty results gracefully

**Rollback If:** Job not running, frequent errors, or causing performance issues

---

## 📋 Pre-Deployment Checklist

### 1. Environment Setup
- [ ] Python 3.12+ installed dan verified
- [ ] Virtual environment created dan activated
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] JobQueue verified: `python -c "from telegram.ext import JobQueue; print('✅ JobQueue available!')"`
- [ ] PostgreSQL 15+ running dan accessible
- [ ] Database schema applied: `psql bot_order -f scripts/schema.sql`
- [ ] `.env` file created dari `.env.example` dengan semua values terisi

### 2. Configuration Validation
- [ ] `TELEGRAM_BOT_TOKEN` valid dan bot responsive
- [ ] `TELEGRAM_ADMIN_IDS` format correct (single integer atau comma-separated)
- [ ] `TELEGRAM_OWNER_IDS` format correct
- [ ] `DATABASE_URL` connection successful
- [ ] `PAKASIR_PROJECT_SLUG` dan `PAKASIR_API_KEY` configured
- [ ] `PAKASIR_PUBLIC_DOMAIN` accessible
- [ ] `BOT_TIMEZONE` set correctly (default: Asia/Jakarta)
- [ ] `DATA_ENCRYPTION_KEY` generated: `openssl rand -base64 32`
- [ ] All optional env vars reviewed dan set jika needed

### 3. Code Quality Verification
- [ ] Run diagnostics: `No errors or warnings detected`
- [ ] No bare exceptions in codebase
- [ ] No SQL injection vulnerabilities
- [ ] All error handling uses specific exception types
- [ ] Proper input validation dan sanitization implemented
- [ ] Code style consistent across all files

---

## 🧪 Functional Testing

### A. Customer User Flow

#### Test 1: Welcome & Onboarding
**Test Steps:**
1. Send `/start` as customer (non-admin user)
2. Verify bot sends sticker first
3. Verify welcome message with HTML formatting:
   - Bold on user name
   - Bold on store name
   - Bold on statistics (Total Pengguna, Transaksi Tuntas)
4. Verify inline keyboard muncul dengan kategori
5. Verify customer reply keyboard muncul (NO `⚙️ Admin Settings` button)
6. Check database: User otomatis di-insert/update di `users` table
7. Check statistics: User count bertambah

**Expected Result:**
- ✅ Sticker received
- ✅ Welcome message dengan proper HTML formatting
- ✅ Statistics accurate dan real-time
- ✅ Customer keyboard tampil (tanpa admin access)
- ✅ User tracked di database

#### Test 2: Product Navigation
**Test Steps:**
1. Click kategori dari inline keyboard
2. Verify product list dengan HTML formatting (bold pada nama produk dan harga)
3. Click nomor produk (1️⃣, 2️⃣, 3️⃣) dari reply keyboard
4. Verify product detail dengan bold field labels (Nama, Harga, Stok, Kategori)
5. Test `➕` button untuk tambah ke cart
6. Test `➖` button untuk kurangi quantity
7. Test quantity shortcuts (✌️ x2, 🖐️ x5, 🔟 x10)

**Expected Result:**
- ✅ Product list formatted correctly dengan HTML
- ✅ Product details dengan bold labels
- ✅ Cart operations work smoothly
- ✅ Stock validation berfungsi

#### Test 3: Cart & Checkout
**Test Steps:**
1. Add multiple products ke cart
2. Click `🧺 Lanjut ke Keranjang`
3. Verify cart summary dengan bold totals dan item counts
4. Test `🎟️ Gunakan Kupon` (jika ada voucher active)
5. Click `💳 Lanjut ke Pembayaran`
6. Verify payment method selection (💠 QRIS, 💼 Saldo)
7. Test cancel operation dengan `❌ Batal`

**Expected Result:**
- ✅ Cart summary accurate dengan HTML formatting
- ✅ Voucher validation works
- ✅ Payment method selection functional
- ✅ Cancel operation returns ke main menu

#### Test 4: Payment Flow (QRIS)
**Test Steps:**
1. Select QRIS payment method
2. Verify loading message: "🎲 Sedang memuat..."
3. Verify invoice creation success dengan:
   - Invoice ID di `<code>` tags (easy copy-paste)
   - Amount di bold
   - QR code atau checkout URL
4. Complete payment via Pakasir (sandbox/production)
5. Verify webhook processing
6. Verify success message dengan bold formatting
7. Verify SNK sent (jika produk punya SNK)

**Expected Result:**
- ✅ Invoice created successfully
- ✅ HTML formatting correct (code tags, bold)
- ✅ Payment processed via webhook
- ✅ Success message received
- ✅ SNK sent jika applicable

#### Test 5: SNK Submission
**Test Steps:**
1. After successful payment, locate SNK message
2. Click `✅ Penuhi SNK` button
3. Send bukti (text atau photo)
4. Verify confirmation message
5. Check admin receives notification dengan bukti

**Expected Result:**
- ✅ SNK button functional
- ✅ Customer dapat submit bukti
- ✅ Admin menerima notification
- ✅ Audit log tercatat

---

### B. Admin User Flow

#### Test 6: Admin Access & Main Menu
**Test Steps:**
1. Send `/start` as admin user (ID in TELEGRAM_ADMIN_IDS)
2. Verify sticker + welcome message dengan admin statistics
3. Verify admin reply keyboard tampil dengan `⚙️ Admin Settings` button
4. Click `⚙️ Admin Settings`
5. Verify main menu dengan 9 submenu:
   - 📝 Kelola Respon Bot
   - 📦 Kelola Produk
   - 📋 Kelola Order
   - 👥 Kelola User
   - 🎟️ Kelola Voucher
   - 📢 Broadcast
   - 🧮 Calculator
   - 📊 Statistik
   - 💰 Deposit

**Expected Result:**
- ✅ Admin keyboard tampil dengan admin button
- ✅ Main menu shows all 9 submenus
- ✅ Inline keyboard navigation works

#### Test 7: Kelola Respon Bot
**Test Steps:**
1. Enter `📝 Kelola Respon Bot` submenu
2. Test preview untuk each template:
   - Welcome message
   - Product message
   - Cart message
   - Payment message
   - Error message
   - Success message
   - SNK message
3. Test edit template teks:
   - Enter edit mode
   - Input new text dengan placeholders
   - Verify placeholder validation
   - Test `❌ Cancel` button
4. Test upload image untuk template
5. Verify changes saved dan applied

**Expected Result:**
- ✅ All templates dapat di-preview
- ✅ Edit mode functional dengan validation
- ✅ Cancel button works
- ✅ Image upload successful
- ✅ Changes persisted di database

#### Test 8: Kelola User
**Test Steps:**
1. Enter `👥 Kelola User` submenu
2. Verify statistics dashboard:
   - Total users (bold)
   - Active users (bold)
   - Blocked users (bold)
3. Test user list dengan pagination
4. Test block user functionality dengan confirmation
5. Test unblock user functionality
6. View user detail dengan transaction history
7. Test navigation buttons

**Expected Result:**
- ✅ Statistics accurate dan formatted
- ✅ Pagination works smoothly
- ✅ Block/unblock operations successful
- ✅ User details comprehensive
- ✅ Navigation intuitive

#### Test 9: Broadcast
**Test Steps:**
1. Enter `📢 Broadcast` submenu
2. Test text broadcast:
   - Input broadcast text
   - Verify preview
   - Confirm send
   - Verify real-time statistics (total, success, failed)
3. Test photo broadcast:
   - Upload photo dengan caption
   - Verify preview
   - Confirm send
4. Test `❌ Cancel` button mid-process
5. Verify broadcast sent ke all users except blocked
6. Check audit log untuk broadcast operation

**Expected Result:**
- ✅ Text broadcast functional
- ✅ Photo broadcast functional
- ✅ Real-time stats displayed
- ✅ Cancel button works
- ✅ Users yang block bot di-skip automatically
- ✅ Audit log complete

#### Test 10: Calculator
**Test Steps:**
1. Enter `🧮 Calculator` submenu
2. Test inline keyboard input:
   - Click number buttons (1, 2, 3, ..., 9, 0)
   - Click operators (+, -, ×, ÷)
   - Test clear button
3. Test refund calculation
4. Test deposit calculation
5. Verify results dengan HTML formatting (bold)

**Expected Result:**
- ✅ Inline keyboard responsive
- ✅ Calculations accurate
- ✅ Results formatted correctly
- ✅ User-friendly interface

#### Test 11: Kelola Voucher
**Test Steps:**
1. Enter `🎟️ Kelola Voucher` submenu
2. Test voucher generation:
   - Nominal voucher (e.g., 10000)
   - Persentase voucher (e.g., 10%)
   - Custom text voucher
3. Verify input validation
4. Test `❌ Cancel` button
5. Verify voucher created dan active
6. Test voucher di customer checkout flow

**Expected Result:**
- ✅ All voucher formats work
- ✅ Validation prevents invalid inputs
- ✅ Cancel button functional
- ✅ Vouchers applicable di checkout

#### Test 12: Kelola Produk
**Test Steps:**
1. Enter `📦 Kelola Produk` submenu
2. Test create new product:
   - Input nama, harga, stok, kategori
   - Verify validation
   - Save product
3. Test edit existing product
4. Test view product statistics
5. Test delete product (jika implemented)

**Expected Result:**
- ✅ CRUD operations functional
- ✅ Statistics accurate
- ✅ Validation prevents bad data

#### Test 13: Kelola Order
**Test Steps:**
1. Enter `📋 Kelola Order` submenu
2. View order list
3. Test filtering by status
4. Test update order status
5. View order details dengan HTML formatting

**Expected Result:**
- ✅ Order list comprehensive
- ✅ Filtering works
- ✅ Status updates successful
- ✅ Details formatted correctly

#### Test 14: Statistik
**Test Steps:**
1. Enter `📊 Statistik` submenu
2. Verify all metrics displayed dengan HTML formatting:
   - Total users (bold)
   - Total orders (bold)
   - Total revenue (bold)
   - Active products (bold)
   - Etc.

**Expected Result:**
- ✅ All statistics accurate
- ✅ HTML formatting applied
- ✅ Real-time data

#### Test 15: Deposit
**Test Steps:**
1. Enter `💰 Deposit` submenu
2. Test manual deposit untuk user
3. Verify inline buttons functional
4. Check deposit reflected di user balance

**Expected Result:**
- ✅ Deposit operations work
- ✅ Balance updates correctly

---

## 🔐 Security Testing

### Test 16: Role-Based Access Control
**Test Steps:**
1. Test as customer user:
   - Verify NO access ke admin menu
   - Try manual commands (jika ada) → should be denied
2. Test as admin user:
   - Verify full access ke admin menu
3. Test with invalid user (not in any list):
   - Verify basic customer access only

**Expected Result:**
- ✅ Customers cannot access admin features
- ✅ Admins have full access
- ✅ Unauthorized users get basic access only

### Test 17: Input Validation
**Test Steps:**
1. Test SQL injection attempts di admin inputs
2. Test XSS attempts di broadcast messages
3. Test invalid data formats (negative prices, invalid dates, etc.)
4. Test overflow/underflow values
5. Test special characters di various inputs

**Expected Result:**
- ✅ No SQL injection possible
- ✅ XSS attempts sanitized
- ✅ Invalid data rejected dengan error messages
- ✅ Special characters handled safely

### Test 18: Anti-Spam Protection
**Test Steps:**
1. Send rapid commands (< 1 second apart) repeatedly
2. Verify spam detection triggered
3. Verify warning message sent ke user
4. Verify notification sent ke admins

**Expected Result:**
- ✅ Spam detected correctly
- ✅ User warned
- ✅ Admins notified

---

## 🔧 System Testing

### Test 19: Database Operations
**Test Steps:**
1. Verify user upsert pada every `/start`
2. Check statistics update real-time
3. Verify audit logs created untuk admin actions
4. Test database connection recovery jika connection lost
5. Verify data integrity (no orphaned records)

**Expected Result:**
- ✅ All database operations successful
- ✅ Data integrity maintained
- ✅ Connection recovery works

### Test 20: JobQueue & Background Tasks
**Test Steps:**
1. Verify JobQueue initialized at startup
2. Check SNK dispatch jobs running (check logs: `[snk_handler]`)
3. Check broadcast queue processing (check logs: `[broadcast_queue]`)
4. Check health check scheduler (check logs: `[healthcheck]`)
5. Test job persistence pada bot restart

**Expected Result:**
- ✅ JobQueue functional
- ✅ All scheduled tasks running
- ✅ No warnings di logs
- ✅ Jobs persist across restarts

### Test 21: Error Handling
**Test Steps:**
1. Test with Pakasir API down/timeout
2. Test with database connection lost
3. Test with invalid webhook payload
4. Test with expired invoices
5. Verify fallback messages sent ke users
6. Verify errors logged appropriately

**Expected Result:**
- ✅ Graceful degradation
- ✅ Users informed dengan friendly messages
- ✅ Errors logged untuk debugging
- ✅ No crashes

### Test 22: Logging & Audit
**Test Steps:**
1. Verify logs created di `logs/telegram-bot/YYYY-MM-DD.log`
2. Check log format: `[timestamp] [level] message`
3. Verify audit logs untuk admin actions
4. Check log rotation (jika implemented)
5. Verify sensitive data NOT logged (passwords, tokens, etc.)

**Expected Result:**
- ✅ All logs properly formatted
- ✅ Audit trail complete
- ✅ No sensitive data exposed
- ✅ Logs rotated correctly

---

## 🚀 Production Readiness

### Test 23: Performance
**Test Steps:**
1. Test dengan multiple concurrent users (simulate load)
2. Measure response times untuk common operations
3. Test broadcast ke large user base (>100 users)
4. Monitor memory usage over time
5. Check database query performance

**Expected Result:**
- ✅ Response times acceptable (< 2s untuk most operations)
- ✅ Broadcast completes successfully
- ✅ No memory leaks
- ✅ Database queries optimized

### Test 24: Backup & Restore
**Test Steps:**
1. Create backup: `python -m src.tools.backup_manager create`
2. Verify backup file created dan encrypted
3. Simulate data loss (staging environment only!)
4. Restore from backup: `python -m src.tools.backup_manager restore`
5. Verify all data restored correctly
6. Document restore time

**Expected Result:**
- ✅ Backup created successfully
- ✅ Restore successful
- ✅ Data integrity maintained
- ✅ Process documented

### Test 25: Health Check
**Test Steps:**
1. Run health check: `python -m src.tools.healthcheck`
2. Verify checks untuk:
   - Telegram API connectivity
   - Database connectivity
   - Disk space
   - Memory usage (jika implemented)
3. Verify alert sent ke owner untuk failures
4. Check health check logs: `logs/health-check/`

**Expected Result:**
- ✅ All health checks pass
- ✅ Alerts work untuk failures
- ✅ Logs comprehensive

### Test 26: Chaos Testing
**Test Steps:**
1. Kill bot process: `pkill -f "python -m src.main"`
2. Verify bot restarts (jika using systemd/docker)
3. Test `docker compose kill` (jika using Docker)
4. Verify container restarts
5. Verify JobQueue jobs resume
6. Check logs untuk any issues

**Expected Result:**
- ✅ Bot recovers gracefully
- ✅ Background jobs resume
- ✅ No data loss
- ✅ Users can continue operations

---

## 📊 Final Verification

### Documentation Review
- [ ] README.md up-to-date
- [ ] CHANGELOG.md complete
- [ ] Release notes (08_release_notes.md) updated
- [ ] Core summary (core_summary.md) accurate
- [ ] PRD (02_prd.md) reflects current implementation
- [ ] fixing_plan.md all issues marked ✅
- [ ] All code comments accurate

### Deployment Checklist
- [ ] All tests passed above
- [ ] Environment variables reviewed dan set
- [ ] Database migrations applied
- [ ] Backup strategy in place
- [ ] Monitoring configured
- [ ] Alert recipients configured (TELEGRAM_OWNER_IDS)
- [ ] Rollback plan documented
- [ ] Team trained on admin menu

### Go-Live Checklist
- [ ] DNS configured (jika using webhooks)
- [ ] SSL certificates valid
- [ ] Firewall rules configured
- [ ] Rate limiting configured
- [ ] Log rotation configured
- [ ] Monitoring dashboards setup
- [ ] On-call schedule established
- [ ] Post-deployment verification plan ready

---

## 🐛 Known Issues & Workarounds

### Issue 1: JobQueue Warning on Fresh Install
**Symptom:** `PTBUserWarning: No 'JobQueue' set up`  
**Fix:** 
```bash
pip uninstall python-telegram-bot -y
pip install -r requirements.txt
python -c "from telegram.ext import JobQueue; print('✅')"
```

### Issue 2: Port Conflicts
**Symptom:** `Address already in use: 9000`  
**Fix:**
```bash
sudo lsof -i :9000
kill <PID>
# Or
sudo fuser -k 9000/tcp
```

### Issue 3: Statistics Not Updating
**Symptom:** User count not incrementing  
**Fix:** Verify `upsert_user()` called di `start()` handler (fixed in v0.2.2)

---

## 📞 Support & Escalation

**Primary Contact:** Owner/Admin  
**Documentation:** `/docs` directory  
**Logs Location:** `/logs/telegram-bot/`  
**Audit Logs:** `/logs/audit/`  
**Health Checks:** `/logs/health-check/`

---

**Testing Completed By:** _______________  
**Date:** _______________  
**Deployment Approved By:** _______________  
**Production Deploy Date:** _______________

---

✅ **All items checked = Ready for Production**