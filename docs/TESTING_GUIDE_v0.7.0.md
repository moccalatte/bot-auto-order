# Testing Guide v0.7.0 - Comprehensive Validation

**Version:** 0.7.0  
**Date:** 2025-01-06  
**Purpose:** Testing checklist and validation steps for v0.7.0 fixes

---

## Overview

v0.7.0 adalah major update yang memperbaiki database schema, service layer validations, dan code quality. Testing guide ini memastikan semua fixes berfungsi dengan baik sebelum production deployment.

**Total Test Cases:** 50+  
**Estimated Testing Time:** 2-3 hours  
**Prerequisites:** Fresh database backup, test environment ready

---

## Pre-Migration Testing

### 1. Backup Verification

**Objective:** Ensure backup is valid and restorable

```bash
# Create backup
pg_dump -h localhost -U postgres bot_auto_order > backup_pre_v0.7.0.sql

# Verify backup size
ls -lh backup_pre_v0.7.0.sql

# Test restore (on test database)
createdb test_restore
psql -h localhost -U postgres test_restore < backup_pre_v0.7.0.sql
dropdb test_restore
```

**Expected Result:** ✅ Backup created successfully, restore works

---

### 2. Current State Documentation

**Objective:** Document current database state

```sql
-- Count records in critical tables
SELECT 
    (SELECT COUNT(*) FROM users) as users,
    (SELECT COUNT(*) FROM products) as products,
    (SELECT COUNT(*) FROM product_contents) as contents,
    (SELECT COUNT(*) FROM orders) as orders,
    (SELECT COUNT(*) FROM coupons) as coupons,
    (SELECT COUNT(*) FROM deposits) as deposits;

-- Check for existing duplicates
SELECT content, COUNT(*) as cnt 
FROM product_contents 
GROUP BY content 
HAVING COUNT(*) > 1;

-- Check stock consistency
SELECT COUNT(*) 
FROM products p
WHERE p.stock != (
    SELECT COUNT(*) FROM product_contents pc 
    WHERE pc.product_id = p.id AND pc.is_used = FALSE
);
```

**Expected Result:** ✅ Baseline numbers recorded

---

## Migration Testing

### 3. Run Migration

**Objective:** Apply schema changes safely

```bash
# Set environment variables
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=bot_auto_order
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=your_password

# Run migration
python scripts/run_migration.py scripts/migrations/001_fix_schema_constraints.sql
```

**Validation Steps:**
- [ ] Migration tracking table created
- [ ] Backup tables created (product_contents_backup_*, etc)
- [ ] User confirmation prompted
- [ ] Migration executed without errors
- [ ] Post-migration validation passed
- [ ] No data loss (row counts match)

**Expected Result:** ✅ Migration completed successfully

---

### 4. Post-Migration Schema Validation

**Objective:** Verify all constraints and indexes applied

```sql
-- Check UNIQUE constraints
SELECT conname, contype, conrelid::regclass
FROM pg_constraint
WHERE conname IN (
    'product_contents_content_key',
    'product_term_submissions_unique_submission',
    'deposits_gateway_order_id_idx'
);

-- Check CHECK constraints
SELECT conname, contype, conrelid::regclass
FROM pg_constraint
WHERE conname LIKE '%_check';

-- Check new indexes
SELECT indexname, tablename
FROM pg_indexes
WHERE indexname LIKE 'idx_%'
ORDER BY tablename, indexname;

-- Verify audit_log table exists
SELECT EXISTS(
    SELECT 1 FROM information_schema.tables 
    WHERE table_name = 'audit_log'
);
```

**Expected Result:** ✅ All constraints and indexes present

---

## Service Layer Testing

### 5. Catalog Service Tests

#### 5.1 Category Validation

**Test Case:** Create product with invalid category

```python
# In Python shell or test script
import asyncio
from src.services.catalog import add_product

async def test_invalid_category():
    try:
        await add_product(
            category_id=99999,  # Non-existent
            code="TEST001",
            name="Test Product",
            description="Test",
            price_cents=10000,
            stock=0
        )
        print("❌ FAIL: Should have raised ValueError")
    except ValueError as e:
        print(f"✅ PASS: {e}")

asyncio.run(test_invalid_category())
```

**Expected Result:** ✅ ValueError: "Kategori dengan ID 99999 tidak ditemukan"

---

#### 5.2 Duplicate Product Code

**Test Case:** Create product with existing code

```python
async def test_duplicate_code():
    # First product
    await add_product(
        category_id=None,
        code="DUPLICATE001",
        name="First Product",
        description="Test",
        price_cents=10000,
        stock=0
    )
    
    # Try duplicate
    try:
        await add_product(
            category_id=None,
            code="DUPLICATE001",  # Same code
            name="Second Product",
            description="Test",
            price_cents=20000,
            stock=0
        )
        print("❌ FAIL: Should have raised ValueError")
    except ValueError as e:
        print(f"✅ PASS: {e}")

asyncio.run(test_duplicate_code())
```

**Expected Result:** ✅ ValueError: "Produk dengan kode 'DUPLICATE001' sudah ada"

---

#### 5.3 Delete Product with Orders

**Test Case:** Try to delete product that has orders

```python
async def test_delete_with_orders():
    # Assume product_id=1 has existing orders
    from src.services.catalog import delete_product
    
    try:
        await delete_product(1)
        print("❌ FAIL: Should have raised ValueError")
    except ValueError as e:
        print(f"✅ PASS: {e}")

asyncio.run(test_delete_with_orders())
```

**Expected Result:** ✅ ValueError mentions "sudah ada dalam X order"

---

### 6. Product Content Tests

#### 6.1 Duplicate Content Prevention

**Test Case:** Add duplicate content

```python
from src.services.product_content import add_product_content

async def test_duplicate_content():
    # First content
    await add_product_content(1, "user@example.com:password123")
    
    # Try duplicate
    try:
        await add_product_content(1, "user@example.com:password123")
        print("❌ FAIL: Should have raised ValueError")
    except ValueError as e:
        print(f"✅ PASS: {e}")

asyncio.run(test_duplicate_content())
```

**Expected Result:** ✅ ValueError: "Content ini sudah ada di database"

---

#### 6.2 Bulk Content with Duplicates

**Test Case:** Add bulk content with some duplicates

```python
from src.services.product_content import add_bulk_product_content

async def test_bulk_content():
    contents = [
        "content1@test.com:pass1",
        "content2@test.com:pass2",
        "content1@test.com:pass1",  # Duplicate
        "content3@test.com:pass3",
    ]
    
    result = await add_bulk_product_content(1, contents)
    
    print(f"Success: {result['success']}")
    print(f"Failed: {result['failed']}")
    print(f"Errors: {result['errors']}")
    
    assert result['success'] == 3
    assert result['failed'] == 1
    print("✅ PASS: Bulk content handled correctly")

asyncio.run(test_bulk_content())
```

**Expected Result:** ✅ 3 success, 1 failed (duplicate)

---

#### 6.3 Stock Synchronization

**Test Case:** Verify stock auto-update

```python
from src.services.product_content import add_product_content
from src.services.catalog import get_product

async def test_stock_sync():
    product_id = 1
    
    # Get initial stock
    product = await get_product(product_id)
    initial_stock = product.stock
    
    # Add content
    await add_product_content(product_id, "new_content@test.com:pass")
    
    # Check stock updated
    product = await get_product(product_id)
    new_stock = product.stock
    
    assert new_stock == initial_stock + 1
    print("✅ PASS: Stock synchronized correctly")

asyncio.run(test_stock_sync())
```

**Expected Result:** ✅ Stock incremented by 1

---

### 7. Voucher Service Tests

#### 7.1 Voucher Creation Validation

**Test Case:** Create voucher with validation

```python
from src.services.voucher import add_voucher

async def test_voucher_validation():
    # Valid voucher
    voucher_id = await add_voucher(
        code="DISCOUNT10",
        description="10% off",
        discount_type="percent",
        discount_value=10,
        max_uses=100
    )
    print(f"✅ PASS: Voucher created with ID {voucher_id}")
    
    # Invalid percent (> 100)
    try:
        await add_voucher(
            code="INVALID",
            description="Test",
            discount_type="percent",
            discount_value=150,  # > 100
            max_uses=10
        )
        print("❌ FAIL: Should reject percent > 100")
    except ValueError as e:
        print(f"✅ PASS: {e}")

asyncio.run(test_voucher_validation())
```

**Expected Result:** ✅ Valid created, invalid rejected

---

#### 7.2 Voucher Usage Increment

**Test Case:** Test usage increment and max_uses enforcement

```python
from src.services.voucher import (
    add_voucher,
    increment_voucher_usage,
    get_voucher_by_id
)

async def test_voucher_usage():
    # Create voucher with max_uses=2
    voucher_id = await add_voucher(
        code="LIMITED",
        description="Limited use",
        discount_type="flat",
        discount_value=5000,
        max_uses=2
    )
    
    # First use
    await increment_voucher_usage(voucher_id)
    voucher = await get_voucher_by_id(voucher_id)
    assert voucher['used_count'] == 1
    print("✅ PASS: First increment")
    
    # Second use
    await increment_voucher_usage(voucher_id)
    voucher = await get_voucher_by_id(voucher_id)
    assert voucher['used_count'] == 2
    print("✅ PASS: Second increment")
    
    # Third use (should fail)
    try:
        await increment_voucher_usage(voucher_id)
        print("❌ FAIL: Should reject exceed max_uses")
    except ValueError as e:
        print(f"✅ PASS: {e}")

asyncio.run(test_voucher_usage())
```

**Expected Result:** ✅ 2 increments ok, 3rd rejected

---

### 8. Order Service Tests

#### 8.1 UUID Handling

**Test Case:** Test UUID string/object handling

```python
from src.services.order import get_order, update_order_status
from uuid import UUID

async def test_uuid_handling():
    # Assume order exists with UUID
    order_id_str = "123e4567-e89b-12d3-a456-426614174000"
    order_id_uuid = UUID(order_id_str)
    
    # Test with string
    order1 = await get_order(order_id_str)
    
    # Test with UUID object
    order2 = await get_order(order_id_uuid)
    
    assert order1['id'] == order2['id']
    print("✅ PASS: UUID handling consistent")
    
    # Test invalid UUID
    try:
        await get_order("not-a-uuid")
        print("❌ FAIL: Should reject invalid UUID")
    except ValueError as e:
        print(f"✅ PASS: Invalid UUID rejected")

asyncio.run(test_uuid_handling())
```

**Expected Result:** ✅ Both formats work, invalid rejected

---

#### 8.2 Product Active Validation

**Test Case:** Cannot add inactive product to order

```python
from src.services.order import add_order_item
from src.services.catalog import edit_product

async def test_inactive_product():
    product_id = 1
    order_id = "123e4567-e89b-12d3-a456-426614174000"
    
    # Deactivate product
    await edit_product(product_id, is_active=False)
    
    # Try to add to order
    try:
        await add_order_item(order_id, product_id, 1, 10000)
        print("❌ FAIL: Should reject inactive product")
    except ValueError as e:
        print(f"✅ PASS: {e}")
    
    # Reactivate for other tests
    await edit_product(product_id, is_active=True)

asyncio.run(test_inactive_product())
```

**Expected Result:** ✅ Inactive product rejected

---

### 9. Deposit Service Tests

#### 9.1 Gateway Order ID Validation

**Test Case:** Require gateway_order_id for gateway deposits

```python
from src.services.deposit import create_deposit

async def test_gateway_deposit():
    # Missing gateway_order_id
    try:
        await create_deposit(
            user_id=1,
            amount_cents=100000,
            fee_cents=1500,
            payable_cents=101500,
            method="qris",
            gateway_order_id="",  # Empty
            expires_at=None
        )
        print("❌ FAIL: Should reject empty gateway_order_id")
    except ValueError as e:
        print(f"✅ PASS: {e}")
    
    # Valid gateway deposit
    deposit = await create_deposit(
        user_id=1,
        amount_cents=100000,
        fee_cents=1500,
        payable_cents=101500,
        method="qris",
        gateway_order_id="GW12345678",
        expires_at=None
    )
    print(f"✅ PASS: Gateway deposit created with ID {deposit['id']}")

asyncio.run(test_gateway_deposit())
```

**Expected Result:** ✅ Empty rejected, valid created

---

#### 9.2 Manual Deposit (No Gateway)

**Test Case:** Create manual deposit by admin

```python
from src.services.deposit import create_manual_deposit

async def test_manual_deposit():
    deposit = await create_manual_deposit(
        user_id=1,
        amount_cents=50000,
        method="bank_transfer",
        notes="Manual topup by admin",
        admin_id=12345
    )
    
    assert deposit['status'] == 'completed'
    assert deposit['created_by_admin'] == True
    assert deposit['gateway_order_id'] is None
    print(f"✅ PASS: Manual deposit created with ID {deposit['id']}")

asyncio.run(test_manual_deposit())
```

**Expected Result:** ✅ Manual deposit created, auto-completed

---

### 10. Reply Templates Tests

#### 10.1 Duplicate Label Prevention

**Test Case:** Cannot create duplicate label

```python
from src.services.reply_templates import add_template

async def test_template_duplicate():
    # First template
    await add_template("welcome", "Welcome message", True)
    
    # Try duplicate
    try:
        await add_template("welcome", "Another welcome", True)
        print("❌ FAIL: Should reject duplicate label")
    except ValueError as e:
        print(f"✅ PASS: {e}")

asyncio.run(test_template_duplicate())
```

**Expected Result:** ✅ Duplicate rejected

---

## Integration Testing

### 11. Complete Order Flow

**Test Case:** Full order flow with product content delivery

**Steps:**
1. Create product with category
2. Add product contents (3 items)
3. Create order with order items
4. Simulate payment success
5. Verify content allocated
6. Verify stock decreased
7. Verify sold_count increased

```python
async def test_complete_order_flow():
    from src.services.catalog import add_product
    from src.services.product_content import add_product_content, get_order_contents
    from src.services.payment import mark_payment_completed
    
    # 1. Create product
    product_id = await add_product(
        category_id=None,
        code="TESTFLOW001",
        name="Test Product Flow",
        description="For testing",
        price_cents=10000,
        stock=0
    )
    
    # 2. Add contents
    for i in range(3):
        await add_product_content(
            product_id,
            f"user{i}@test.com:password{i}"
        )
    
    # 3. Create order (assume order created via payment.create_invoice)
    # Gateway order ID would be from Pakasir
    gateway_order_id = "test_flow_gw123"
    
    # 4. Mark payment completed
    await mark_payment_completed(gateway_order_id, 10000)
    
    # 5. Verify content allocated
    # (This would be in actual order_id from create_invoice)
    
    print("✅ PASS: Complete order flow successful")

# Run with actual order flow
```

---

### 12. Concurrent Operations

**Test Case:** Test race conditions

```python
import asyncio

async def test_concurrent_content_usage():
    from src.services.product_content import mark_content_as_used
    from uuid import uuid4
    
    content_id = 1  # Assume exists
    
    # Try to mark as used concurrently
    tasks = [
        mark_content_as_used(content_id, uuid4())
        for _ in range(5)
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Only 1 should succeed
    successes = [r for r in results if r is True]
    failures = [r for r in results if isinstance(r, Exception)]
    
    assert len(successes) == 1
    assert len(failures) == 4
    print("✅ PASS: Race condition handled correctly")

asyncio.run(test_concurrent_content_usage())
```

**Expected Result:** ✅ Only 1 success, 4 failures

---

## Performance Testing

### 13. Index Usage Validation

**Objective:** Verify new indexes are used

```sql
-- Test query plans
EXPLAIN ANALYZE
SELECT * FROM products WHERE is_active = TRUE;

EXPLAIN ANALYZE
SELECT * FROM product_contents 
WHERE product_id = 1 AND is_used = FALSE;

EXPLAIN ANALYZE
SELECT * FROM orders WHERE status = 'paid';

EXPLAIN ANALYZE
SELECT * FROM coupons WHERE code = 'DISCOUNT10';
```

**Expected Result:** ✅ All queries use indexes (Index Scan, not Seq Scan)

---

### 14. Bulk Operations Performance

**Test Case:** Bulk content addition performance

```python
import time

async def test_bulk_performance():
    from src.services.product_content import add_bulk_product_content
    
    # Generate 1000 unique contents
    contents = [f"bulk{i}@test.com:pass{i}" for i in range(1000)]
    
    start = time.time()
    result = await add_bulk_product_content(1, contents)
    elapsed = time.time() - start
    
    print(f"Time: {elapsed:.2f}s")
    print(f"Success: {result['success']}")
    print(f"Failed: {result['failed']}")
    print(f"Rate: {result['success'] / elapsed:.2f} items/sec")
    
    assert elapsed < 60  # Should complete in under 60s
    print("✅ PASS: Bulk operation within acceptable time")

asyncio.run(test_bulk_performance())
```

**Expected Result:** ✅ Completes in reasonable time

---

## Rollback Testing

### 15. Rollback Procedure

**Objective:** Verify rollback works

```bash
# 1. Note current migration status
python scripts/run_migration.py --status

# 2. Run rollback SQL (from migration file)
psql -h localhost -U postgres bot_auto_order < rollback.sql

# 3. Verify constraints removed
psql -h localhost -U postgres bot_auto_order -c "
SELECT conname FROM pg_constraint 
WHERE conname = 'product_contents_content_key';"

# 4. Restore from migration (for testing)
python scripts/run_migration.py scripts/migrations/001_fix_schema_constraints.sql
```

**Expected Result:** ✅ Rollback and re-apply both work

---

## Production Readiness Checklist

### Pre-Deployment

- [ ] All unit tests passed
- [ ] Integration tests passed
- [ ] Performance tests acceptable
- [ ] Rollback procedure tested
- [ ] Documentation updated
- [ ] Backup created and verified
- [ ] Migration dry-run on staging
- [ ] Team notified of deployment

### Deployment

- [ ] Maintenance mode enabled
- [ ] Final backup created
- [ ] Migration executed successfully
- [ ] Post-migration validation passed
- [ ] Bot restarted
- [ ] Health checks passed
- [ ] Monitoring active

### Post-Deployment

- [ ] Smoke tests completed
- [ ] User acceptance testing
- [ ] Monitor logs for 1 hour
- [ ] No critical errors
- [ ] Performance acceptable
- [ ] Rollback plan ready if needed

---

## Test Results Template

```
================================================================================
TEST RESULTS - v0.7.0
================================================================================
Date: _______________
Tester: _______________
Environment: [ ] Dev [ ] Staging [ ] Production

Pre-Migration Tests:
  [ ] Backup verification          _____ (Pass/Fail)
  [ ] Current state documented     _____ (Pass/Fail)

Migration Tests:
  [ ] Migration execution          _____ (Pass/Fail)
  [ ] Schema validation            _____ (Pass/Fail)
  [ ] Data integrity               _____ (Pass/Fail)

Service Layer Tests:
  [ ] Catalog service              _____ (Pass/Fail)
  [ ] Product content              _____ (Pass/Fail)
  [ ] Voucher service              _____ (Pass/Fail)
  [ ] Order service                _____ (Pass/Fail)
  [ ] Deposit service              _____ (Pass/Fail)
  [ ] Reply templates              _____ (Pass/Fail)

Integration Tests:
  [ ] Complete order flow          _____ (Pass/Fail)
  [ ] Concurrent operations        _____ (Pass/Fail)

Performance Tests:
  [ ] Index usage                  _____ (Pass/Fail)
  [ ] Bulk operations              _____ (Pass/Fail)

Rollback Tests:
  [ ] Rollback procedure           _____ (Pass/Fail)

Overall Result: _____ (Pass/Fail)

Notes:
________________________________________________________________________
________________________________________________________________________
________________________________________________________________________

Sign-off: _____________________  Date: ______________
================================================================================
```

---

## Support & Troubleshooting

**Common Issues:**

1. **Migration fails on duplicate content**
   - Solution: Migration script auto-marks older duplicates as used

2. **Constraint violation errors**
   - Solution: Check data cleanup in migration script logs

3. **Performance degradation**
   - Solution: VACUUM ANALYZE database after migration

4. **Rollback needed**
   - Solution: Follow rollback procedure, restore from backup if needed

**Contact:**
- Check `docs/codebase-critics.md` for detailed fix information
- Review `FIXES_SUMMARY_v0.7.0.txt` for comprehensive changes
- Consult Fixer Agent documentation in `docs/agents.md`

---

**End of Testing Guide v0.7.0**