# Deployment Checklist v0.7.0

**Version:** 0.7.0  
**Date:** 2025-01-06  
**Type:** Major Update - Schema & Service Layer Overhaul  
**Estimated Downtime:** 15-20 minutes  
**Risk Level:** 🟢 LOW (Safe migration with rollback)

---

## ⚠️ CRITICAL: Read Before Proceeding

**This checklist MUST be followed in order. Do not skip steps.**

**Stop Deployment If:**
- ❌ Backup fails or cannot be verified
- ❌ Database connection issues
- ❌ Migration script not found
- ❌ Team not available for support

---

## 📋 Pre-Deployment Checklist

### Environment Preparation

- [ ] **1.1** Verify production environment access
  ```bash
  ssh user@production-server
  cd /path/to/bot-auto-order
  ```

- [ ] **1.2** Check current bot status
  ```bash
  systemctl status bot-auto-order
  # Should be: active (running)
  ```

- [ ] **1.3** Verify database connectivity
  ```bash
  psql -h localhost -U postgres -d bot_auto_order -c "SELECT version();"
  # Should return PostgreSQL version
  ```

- [ ] **1.4** Check disk space (minimum 5GB free)
  ```bash
  df -h
  # Verify sufficient space for backup
  ```

- [ ] **1.5** Verify Python and dependencies
  ```bash
  python3 --version  # Should be 3.10+
  pip list | grep asyncpg
  ```

---

### Team Coordination

- [ ] **2.1** Schedule deployment window (recommended: low traffic hours)
  - **Scheduled Time:** _____________ (Date & Time)
  - **Duration:** 1 hour (includes buffer)

- [ ] **2.2** Notify stakeholders
  - [ ] Business owner
  - [ ] Customer support team
  - [ ] Admin users
  - [ ] Technical team

- [ ] **2.3** Prepare maintenance message
  ```
  "🔧 Bot sedang dalam maintenance untuk upgrade sistem.
  Estimasi selesai: [TIME]. Terima kasih atas pengertiannya!"
  ```

- [ ] **2.4** Ensure backup team available
  - [ ] Primary: ________________
  - [ ] Backup: ________________

---

### Code & Files Verification

- [ ] **3.1** Pull latest code from repository
  ```bash
  git fetch origin
  git checkout main
  git pull origin main
  ```

- [ ] **3.2** Verify v0.7.0 tag/branch
  ```bash
  git log --oneline -1
  # Should show v0.7.0 related commit
  ```

- [ ] **3.3** Check migration files exist
  ```bash
  ls -la scripts/migrations/001_fix_schema_constraints.sql
  ls -la scripts/run_migration.py
  # Both files should exist
  ```

- [ ] **3.4** Review documentation
  - [ ] FIXES_SUMMARY_v0.7.0.txt
  - [ ] TESTING_GUIDE_v0.7.0.md
  - [ ] RELEASE_v0.7.0_EXECUTIVE_SUMMARY.md

---

### Database Backup

- [ ] **4.1** Create full database backup
  ```bash
  pg_dump -h localhost -U postgres \
    -F c -b -v \
    -f backup_v0.7.0_$(date +%Y%m%d_%H%M%S).dump \
    bot_auto_order
  ```

- [ ] **4.2** Verify backup file created
  ```bash
  ls -lh backup_v0.7.0_*.dump
  # Should show file size (should be > 1MB if data exists)
  ```

- [ ] **4.3** Test backup restoration (on test DB)
  ```bash
  # Create test database
  createdb test_restore_v070
  
  # Restore backup
  pg_restore -h localhost -U postgres \
    -d test_restore_v070 \
    backup_v0.7.0_*.dump
  
  # Verify
  psql -h localhost -U postgres test_restore_v070 -c "\dt"
  
  # Cleanup
  dropdb test_restore_v070
  ```

- [ ] **4.4** Copy backup to safe location
  ```bash
  cp backup_v0.7.0_*.dump /backup/safe-location/
  # Or upload to cloud storage
  ```

- [ ] **4.5** Document backup details
  - **Backup File:** _______________________________
  - **File Size:** _______________________________
  - **Timestamp:** _______________________________
  - **Location:** _______________________________

---

### Current State Documentation

- [ ] **5.1** Record current row counts
  ```sql
  SELECT 
    (SELECT COUNT(*) FROM users) as users,
    (SELECT COUNT(*) FROM products) as products,
    (SELECT COUNT(*) FROM product_contents) as contents,
    (SELECT COUNT(*) FROM orders) as orders,
    (SELECT COUNT(*) FROM coupons) as coupons,
    (SELECT COUNT(*) FROM deposits) as deposits;
  ```
  - **Users:** _______
  - **Products:** _______
  - **Contents:** _______
  - **Orders:** _______
  - **Coupons:** _______
  - **Deposits:** _______

- [ ] **5.2** Check for existing duplicates
  ```sql
  -- Duplicate contents
  SELECT COUNT(*) FROM (
    SELECT content, COUNT(*) as cnt 
    FROM product_contents 
    GROUP BY content 
    HAVING COUNT(*) > 1
  ) dups;
  ```
  - **Duplicate Contents:** _______ (migration will fix)

- [ ] **5.3** Check stock consistency
  ```sql
  SELECT COUNT(*) FROM products p
  WHERE p.stock != (
    SELECT COUNT(*) FROM product_contents pc 
    WHERE pc.product_id = p.id AND pc.is_used = FALSE
  );
  ```
  - **Stock Mismatches:** _______ (migration will fix)

---

## 🚀 Deployment Steps

### Step 1: Enable Maintenance Mode

- [ ] **6.1** Stop bot service
  ```bash
  systemctl stop bot-auto-order
  ```

- [ ] **6.2** Verify bot stopped
  ```bash
  systemctl status bot-auto-order
  # Should be: inactive (dead)
  ```

- [ ] **6.3** Post maintenance message (if bot has broadcast feature)
  ```bash
  # Or manually inform users via other channels
  ```

- [ ] **6.4** Record downtime start
  - **Downtime Started:** _____________ (Time)

---

### Step 2: Run Migration

- [ ] **7.1** Set environment variables
  ```bash
  export POSTGRES_HOST=localhost
  export POSTGRES_PORT=5432
  export POSTGRES_DB=bot_auto_order
  export POSTGRES_USER=postgres
  export POSTGRES_PASSWORD=your_password_here
  ```

- [ ] **7.2** Verify variables
  ```bash
  echo $POSTGRES_HOST
  echo $POSTGRES_DB
  ```

- [ ] **7.3** Run migration script
  ```bash
  python3 scripts/run_migration.py scripts/migrations/001_fix_schema_constraints.sql
  ```

- [ ] **7.4** Review migration output
  - [ ] Migration tracking table created
  - [ ] Backup tables created (automatic)
  - [ ] Data cleanup completed (duplicates handled)
  - [ ] Constraints applied successfully
  - [ ] Indexes created successfully
  - [ ] Validation checks passed
  - [ ] No errors reported

- [ ] **7.5** Record migration completion
  - **Migration Time:** _____________ (duration)
  - **Status:** _____________ (success/failed)

---

### Step 3: Verify Database Changes

- [ ] **8.1** Check constraints applied
  ```sql
  SELECT conname, contype FROM pg_constraint 
  WHERE conname IN (
    'product_contents_content_key',
    'product_term_submissions_unique_submission',
    'check_used_count_non_negative',
    'check_used_count_le_max_uses'
  );
  ```
  - **Constraints Count:** _______ (should be 4+)

- [ ] **8.2** Check indexes created
  ```sql
  SELECT COUNT(*) FROM pg_indexes 
  WHERE indexname LIKE 'idx_%';
  ```
  - **Indexes Count:** _______ (should be 25+)

- [ ] **8.3** Verify audit_log table
  ```sql
  SELECT EXISTS(
    SELECT 1 FROM information_schema.tables 
    WHERE table_name = 'audit_log'
  );
  ```
  - **Audit Log Exists:** _______ (should be true)

- [ ] **8.4** Verify data integrity
  ```sql
  -- Check no data lost
  SELECT 
    (SELECT COUNT(*) FROM users) as users,
    (SELECT COUNT(*) FROM products) as products,
    (SELECT COUNT(*) FROM orders) as orders;
  ```
  - **Row counts match pre-migration:** _______ (yes/no)

---

### Step 4: Update Code & Dependencies

- [ ] **9.1** Install/update dependencies (if any)
  ```bash
  pip install -r requirements.txt
  ```

- [ ] **9.2** Run database migrations (if separate from schema)
  ```bash
  # Usually not needed for v0.7.0, schema migration covers all
  ```

- [ ] **9.3** Clear Python cache
  ```bash
  find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
  find . -type f -name "*.pyc" -delete
  ```

---

### Step 5: Start Bot & Verify

- [ ] **10.1** Start bot service
  ```bash
  systemctl start bot-auto-order
  ```

- [ ] **10.2** Check service status
  ```bash
  systemctl status bot-auto-order
  # Should be: active (running)
  ```

- [ ] **10.3** Monitor logs for errors
  ```bash
  journalctl -u bot-auto-order -f -n 50
  # Should show startup messages, no errors
  ```

- [ ] **10.4** Wait 2 minutes for full startup

- [ ] **10.5** Record downtime end
  - **Downtime Ended:** _____________ (Time)
  - **Total Downtime:** _____________ (minutes)

---

## ✅ Post-Deployment Validation

### Smoke Tests (Critical)

- [ ] **11.1** Bot responds to commands
  - [ ] Send `/start` to bot
  - [ ] Bot responds with welcome message
  - [ ] Inline keyboard appears

- [ ] **11.2** Test product listing
  - [ ] Open product menu
  - [ ] Products display correctly
  - [ ] Stock numbers accurate

- [ ] **11.3** Test product creation (admin)
  - [ ] Create test product with category
  - [ ] Should succeed with valid data
  - [ ] Try duplicate code - should fail with clear error

- [ ] **11.4** Test content addition (admin)
  - [ ] Add content to test product
  - [ ] Stock auto-increments
  - [ ] Try duplicate content - should fail with clear error

- [ ] **11.5** Test voucher system
  - [ ] Create test voucher with max_uses=2
  - [ ] Usage counter works
  - [ ] Cannot exceed max_uses

- [ ] **11.6** Test order flow (if possible)
  - [ ] Create test order
  - [ ] Product validation works (active status)
  - [ ] Order completes successfully

---

### Database Integrity Checks

- [ ] **12.1** Run integrity check
  ```sql
  -- Check for duplicate contents (should be 0)
  SELECT COUNT(*) FROM (
    SELECT content, COUNT(*) as cnt 
    FROM product_contents 
    GROUP BY content 
    HAVING COUNT(*) > 1
  ) dups;
  ```
  - **Duplicates:** _______ (should be 0)

- [ ] **12.2** Check stock synchronization
  ```sql
  -- Stock mismatches (should be 0)
  SELECT COUNT(*) FROM products p
  WHERE p.stock != (
    SELECT COUNT(*) FROM product_contents pc 
    WHERE pc.product_id = p.id AND pc.is_used = FALSE
  );
  ```
  - **Mismatches:** _______ (should be 0)

- [ ] **12.3** Check orphaned data
  ```sql
  -- Orphaned order_items (should be 0)
  SELECT COUNT(*) FROM order_items oi
  LEFT JOIN products p ON oi.product_id = p.id
  WHERE p.id IS NULL;
  ```
  - **Orphans:** _______ (should be 0)

---

### Performance Checks

- [ ] **13.1** Monitor CPU usage
  ```bash
  top -bn1 | grep bot-auto-order
  # Should be normal (<50% CPU)
  ```

- [ ] **13.2** Monitor memory usage
  ```bash
  ps aux | grep python3 | grep bot-auto-order
  # Should be normal (<500MB RSS)
  ```

- [ ] **13.3** Check database query performance
  ```sql
  -- Test index usage
  EXPLAIN ANALYZE SELECT * FROM products WHERE is_active = TRUE;
  -- Should use Index Scan (not Seq Scan)
  ```

- [ ] **13.4** Response time check
  - Bot responds within 2 seconds: _______

---

### Log Review

- [ ] **14.1** Check error logs (last 30 minutes)
  ```bash
  journalctl -u bot-auto-order --since "30 minutes ago" | grep ERROR
  # Should be empty or minimal
  ```

- [ ] **14.2** Check warning logs
  ```bash
  journalctl -u bot-auto-order --since "30 minutes ago" | grep WARN
  # Should be minimal
  ```

- [ ] **14.3** Check migration logs
  ```bash
  psql -h localhost -U postgres bot_auto_order -c \
    "SELECT * FROM schema_migrations ORDER BY executed_at DESC LIMIT 1;"
  ```
  - **Migration Status:** _______ (should be 'success')

---

## 📊 Post-Deployment Monitoring (First 24 Hours)

### Hour 1 (Critical)

- [ ] **15.1** Monitor active transactions
- [ ] **15.2** Watch for error spikes
- [ ] **15.3** Verify customer orders processing
- [ ] **15.4** Check admin operations working

### Hour 2-6 (Important)

- [ ] **15.5** Monitor system performance
- [ ] **15.6** Track error rates
- [ ] **15.7** Review customer feedback
- [ ] **15.8** Verify voucher usage tracking

### Hour 6-24 (Normal)

- [ ] **15.9** Daily metrics review
- [ ] **15.10** Stock synchronization verification
- [ ] **15.11** Database performance check
- [ ] **15.12** User satisfaction monitoring

---

## 🚨 Rollback Procedure (If Needed)

**Execute ONLY if critical issues found:**

### Quick Rollback

- [ ] **16.1** Stop bot immediately
  ```bash
  systemctl stop bot-auto-order
  ```

- [ ] **16.2** Restore database from backup
  ```bash
  # Drop current database (CAREFUL!)
  dropdb bot_auto_order
  
  # Recreate
  createdb bot_auto_order
  
  # Restore from backup
  pg_restore -h localhost -U postgres \
    -d bot_auto_order \
    backup_v0.7.0_TIMESTAMP.dump
  ```

- [ ] **16.3** Revert code changes
  ```bash
  git checkout previous-stable-version
  # Or restore from backup
  ```

- [ ] **16.4** Start bot
  ```bash
  systemctl start bot-auto-order
  ```

- [ ] **16.5** Verify rollback successful
- [ ] **16.6** Notify team and stakeholders
- [ ] **16.7** Document issues encountered

---

## 📝 Post-Deployment Report

### Deployment Summary

- **Deployment Date:** _____________
- **Start Time:** _____________
- **End Time:** _____________
- **Total Duration:** _____________ minutes
- **Downtime:** _____________ minutes
- **Status:** _____________ (Success/Failed/Rolled Back)

### Migration Results

- **Row Counts Match:** _______ (Yes/No)
- **Constraints Applied:** _______ (Count)
- **Indexes Created:** _______ (Count)
- **Data Integrity:** _______ (Pass/Fail)
- **Performance:** _______ (Normal/Degraded/Improved)

### Issues Encountered

1. _____________________________________________
2. _____________________________________________
3. _____________________________________________

### Resolutions Applied

1. _____________________________________________
2. _____________________________________________
3. _____________________________________________

### Smoke Test Results

- [ ] Bot Responding: _______
- [ ] Product Listing: _______
- [ ] Product Creation: _______
- [ ] Content Addition: _______
- [ ] Voucher System: _______
- [ ] Order Flow: _______

### Team Sign-Off

- **Deployed By:** _______________ Date: _______________
- **Verified By:** _______________ Date: _______________
- **Approved By:** _______________ Date: _______________

---

## 📚 Reference Documents

- **Fixes Summary:** `FIXES_SUMMARY_v0.7.0.txt`
- **Testing Guide:** `docs/TESTING_GUIDE_v0.7.0.md`
- **Executive Summary:** `RELEASE_v0.7.0_EXECUTIVE_SUMMARY.md`
- **Critics Report:** `docs/codebase-critics.md`
- **Quick Reference:** `docs/QUICK_REFERENCE.md`

---

## 🔗 Support Contacts

**During Deployment:**
- **Primary:** Technical Lead - [contact]
- **Backup:** Senior Developer - [contact]
- **Escalation:** Business Owner - [contact]

**Post-Deployment:**
- **Issues:** Submit to issue tracker
- **Questions:** Contact development team
- **Emergency:** Use emergency contact list

---

## ✅ Final Checklist

Before marking deployment complete:

- [ ] All critical smoke tests passed
- [ ] No errors in logs (or acceptable only)
- [ ] Performance normal or improved
- [ ] Team notified of completion
- [ ] Monitoring active
- [ ] Post-deployment report completed
- [ ] Documentation updated
- [ ] Celebration! 🎉

---

**Status:** _____________ (Complete/In Progress/Rolled Back)  
**Signed:** _______________ Date: _______________

---

**END OF DEPLOYMENT CHECKLIST v0.7.0**

🚀 **Good luck with your deployment!**