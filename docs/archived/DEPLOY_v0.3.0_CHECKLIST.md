# 🚀 DEPLOYMENT CHECKLIST v0.3.0

**Target Version:** v0.3.0  
**Deployment Date:** _____________  
**Deployed By:** _____________

---

## PRE-DEPLOYMENT

### 1. Backup (5 min)
- [ ] Backup database
  ```bash
  pg_dump bot_auto_order > backup_$(date +%Y%m%d_%H%M%S).sql
  ```
- [ ] Backup `.env` file
  ```bash
  cp .env .env.backup_$(date +%Y%m%d)
  ```
- [ ] Note current bot version: __________

### 2. Code Review (5 min)
- [ ] Verify on correct branch: `main`
- [ ] Check latest commit hash: __________
- [ ] Review CHANGELOG.md v0.3.0 entry
- [ ] Review fixing_plan.md status

### 3. Environment Check (2 min)
- [ ] Bot currently running? Yes / No
- [ ] Database accessible? Yes / No
- [ ] Telegram API reachable? Yes / No

---

## DEPLOYMENT

### 4. Pull Latest Code (2 min)
```bash
cd /path/to/bot-auto-order
git fetch origin
git pull origin main
```
- [ ] Code pulled successfully
- [ ] No merge conflicts

### 5. Verify Files Changed (2 min)
```bash
git log --oneline -5
git diff HEAD~1 --stat
```
Expected files:
- [ ] `src/bot/handlers.py`
- [ ] `src/bot/admin/admin_menu.py`
- [ ] `src/bot/admin/admin_actions.py`
- [ ] Documentation files updated

### 6. Syntax Check (1 min)
```bash
python -m py_compile src/bot/handlers.py
python -m py_compile src/bot/admin/admin_menu.py
python -m py_compile src/bot/admin/admin_actions.py
```
- [ ] All files compiled successfully
- [ ] No syntax errors

### 7. Restart Bot (2 min)

**Option A: Systemd**
```bash
sudo systemctl restart telegram-bot
sudo systemctl status telegram-bot
```

**Option B: Manual**
```bash
pkill -f "python -m src.main"
sleep 2
python -m src.main --mode polling &
```

**Option C: Docker**
```bash
docker-compose restart bot
docker-compose logs -f bot
```

- [ ] Bot restarted successfully
- [ ] No errors in startup logs

---

## POST-DEPLOYMENT TESTING

### 8. Customer Flow (5 min)
- [ ] Send `/start` as customer
- [ ] Verify: Stiker received
- [ ] Verify: Welcome message received
- [ ] Verify: Reply keyboard displayed
- [ ] Verify: Inline keyboard with "🏷 Cek Stok" & "🛍 Semua Produk"
- [ ] Click "🏷 Cek Stok" → Product list shown
- [ ] Click "🛍 Semua Produk" → Catalog shown

**Status:** ✅ Pass / ❌ Fail  
**Notes:** _________________________

### 9. Admin Flow - Product Management (10 min)
- [ ] Send `/start` as admin
- [ ] Verify: Admin keyboard displayed
- [ ] Go to "⚙️ Admin Settings"
- [ ] Go to "🛒 Kelola Produk"
- [ ] Click "➕ Tambah Produk"
- [ ] Complete step 1/5: Kode produk
- [ ] Complete step 2/5: Nama produk
- [ ] Complete step 3/5: Harga produk
- [ ] Complete step 4/5: Stok produk
- [ ] Complete step 5/5: Deskripsi (or skip with `-`)
- [ ] Verify: Product created successfully (no error!)
- [ ] Test cancel button in middle of wizard
- [ ] Verify: Cancel returns to welcome message

**Status:** ✅ Pass / ❌ Fail  
**Notes:** _________________________

### 10. Admin Flow - Voucher (5 min)
- [ ] Go to "🎟️ Kelola Voucher"
- [ ] Click "➕ Generate Voucher Baru"
- [ ] Test format: `TEST10 | 10% | 100`
- [ ] Verify: Voucher created successfully
- [ ] Verify: Response shows preview (kode, diskon, max pakai)
- [ ] Click "➕ Generate Voucher Baru" again
- [ ] Test format: `HEMAT5K | 5000 | 50`
- [ ] Verify: Voucher created successfully
- [ ] Test invalid format: `INVALID`
- [ ] Verify: Error message shown
- [ ] Test cancel button
- [ ] Verify: Cancel returns to welcome message

**Status:** ✅ Pass / ❌ Fail  
**Notes:** _________________________

### 11. Admin Flow - Cancel Consistency (5 min)
- [ ] Enter "🛒 Kelola Produk" menu
- [ ] Start "➕ Tambah Produk"
- [ ] Click "❌ Batal" at step 2
- [ ] Verify: Welcome message shown with stats
- [ ] Enter "📣 Broadcast Pesan"
- [ ] Verify: Cancel button is inline (not reply keyboard)
- [ ] Click "❌ Batal Broadcast"
- [ ] Verify: Welcome message shown
- [ ] Test cancel in other menus (Calculator, Voucher, etc)
- [ ] Verify: All cancel buttons consistent

**Status:** ✅ Pass / ❌ Fail  
**Notes:** _________________________

### 12. Admin Flow - Statistics (2 min)
- [ ] Go to "📊 Statistik"
- [ ] Verify: No crash or error
- [ ] Verify: Shows total pengguna
- [ ] Verify: Shows total transaksi
- [ ] Verify: Shows total produk
- [ ] Verify: Numbers are accurate

**Status:** ✅ Pass / ❌ Fail  
**Notes:** _________________________

### 13. Admin Flow - Other Features (5 min)
- [ ] Test "📝 Edit Produk" → Select → Edit field → Save
- [ ] Test "🗑️ Hapus Produk" → Select → Confirm → Delete
- [ ] Test "📜 Kelola SNK Produk" → Select product → Input SNK
- [ ] Test "🧮 Calculator" → Hitung Refund flow
- [ ] Test "⬅️ Kembali ke Menu Utama"

**Status:** ✅ Pass / ❌ Fail  
**Notes:** _________________________

---

## MONITORING

### 14. Log Monitoring (10 min)
```bash
tail -f logs/telegram-bot/$(date +%Y-%m-%d).log
```

Monitor for:
- [ ] No ERROR level logs
- [ ] No unexpected exceptions
- [ ] User actions logging correctly
- [ ] Database queries executing

**Status:** ✅ Pass / ❌ Fail  
**Notes:** _________________________

### 15. Performance Check (5 min)
- [ ] Bot responds within 2 seconds
- [ ] No timeout errors
- [ ] Database queries fast
- [ ] Memory usage normal

**Status:** ✅ Pass / ❌ Fail  
**Notes:** _________________________

---

## ROLLBACK (IF NEEDED)

### If Tests Fail

**1. Restore Previous Version**
```bash
git log --oneline -10
git checkout <previous_commit_hash>
sudo systemctl restart telegram-bot
```

**2. Restore Database (if needed)**
```bash
psql bot_auto_order < backup_YYYYMMDD_HHMMSS.sql
```

**3. Notify Team**
- Document the issue
- Create bug report
- Plan fix deployment

---

## SIGN-OFF

### Deployment Summary
- **Start Time:** __________
- **End Time:** __________
- **Duration:** ________ minutes
- **Status:** ✅ Success / ❌ Failed / ⚠️ Partial

### Test Results Summary
- Customer Flow: ✅ / ❌
- Product Management: ✅ / ❌
- Voucher Generation: ✅ / ❌
- Cancel Consistency: ✅ / ❌
- Statistics: ✅ / ❌
- Other Features: ✅ / ❌
- Log Monitoring: ✅ / ❌
- Performance: ✅ / ❌

### Issues Encountered
1. _________________________
2. _________________________
3. _________________________

### Final Decision
- [ ] ✅ APPROVED - Deployment successful, all tests passed
- [ ] ⚠️ CONDITIONAL - Deployment successful with minor issues
- [ ] ❌ ROLLBACK - Critical issues found, rolled back

### Signatures
**Deployed By:** _____________ Date: _______  
**Tested By:** _____________ Date: _______  
**Approved By:** _____________ Date: _______

---

## POST-DEPLOYMENT ACTIONS

### Immediate (within 1 hour)
- [ ] Monitor logs for errors
- [ ] Check user feedback/complaints
- [ ] Verify critical flows working

### Short-term (within 24 hours)
- [ ] Monitor overall bot health
- [ ] Check database performance
- [ ] Review audit logs
- [ ] Collect user feedback

### Long-term (within 1 week)
- [ ] Analyze usage patterns
- [ ] Review error rates
- [ ] Plan next improvements
- [ ] Update documentation if needed

---

**Document Version:** 1.0  
**Last Updated:** 2025-01-XX  
**Next Review:** After deployment