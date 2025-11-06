-- Migration: 001_fix_schema_constraints.sql
-- Description: Apply schema fixes from critic agent findings
-- Date: 2025-01-XX
-- Author: Fixer Agent
--
-- This migration adds:
-- 1. UNIQUE constraint on product_contents.content
-- 2. UNIQUE constraint on product_term_submissions
-- 3. Improved constraints on coupons (used_count validation)
-- 4. Better deposit schema with gateway_order_id
-- 5. Additional indexes for performance
-- 6. Audit log table
--
-- IMPORTANT: This migration is designed to be safe and reversible
-- Run with caution on production data

-- ============================================================================
-- PHASE 1: BACKUP & VALIDATION
-- ============================================================================

-- Create backup tables (optional, uncomment if needed)
-- CREATE TABLE IF NOT EXISTS product_contents_backup_20250106 AS SELECT * FROM product_contents;
-- CREATE TABLE IF NOT EXISTS product_term_submissions_backup_20250106 AS SELECT * FROM product_term_submissions;
-- CREATE TABLE IF NOT EXISTS coupons_backup_20250106 AS SELECT * FROM coupons;
-- CREATE TABLE IF NOT EXISTS deposits_backup_20250106 AS SELECT * FROM deposits;

-- ============================================================================
-- PHASE 2: DATA CLEANUP (Fix duplicates before adding constraints)
-- ============================================================================

-- Check for duplicate product contents
DO $$
DECLARE
    dup_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO dup_count
    FROM (
        SELECT content, COUNT(*) as cnt
        FROM product_contents
        GROUP BY content
        HAVING COUNT(*) > 1
    ) dups;

    IF dup_count > 0 THEN
        RAISE NOTICE 'WARNING: Found % duplicate product contents. Marking older duplicates as used.', dup_count;

        -- Mark older duplicates as used (keep newest one)
        UPDATE product_contents pc1
        SET is_used = TRUE,
            used_at = NOW()
        WHERE is_used = FALSE
        AND EXISTS (
            SELECT 1 FROM product_contents pc2
            WHERE pc2.content = pc1.content
            AND pc2.id > pc1.id
        );
    END IF;
END $$;

-- Check for duplicate product_term_submissions
DO $$
DECLARE
    dup_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO dup_count
    FROM (
        SELECT order_id, product_id, telegram_user_id, COUNT(*) as cnt
        FROM product_term_submissions
        GROUP BY order_id, product_id, telegram_user_id
        HAVING COUNT(*) > 1
    ) dups;

    IF dup_count > 0 THEN
        RAISE NOTICE 'WARNING: Found % duplicate term submissions. Keeping newest submission.', dup_count;

        -- Delete older duplicate submissions (keep newest one)
        DELETE FROM product_term_submissions pts1
        WHERE EXISTS (
            SELECT 1 FROM product_term_submissions pts2
            WHERE pts2.order_id = pts1.order_id
            AND pts2.product_id = pts1.product_id
            AND pts2.telegram_user_id = pts1.telegram_user_id
            AND pts2.id > pts1.id
        );
    END IF;
END $$;

-- ============================================================================
-- PHASE 3: SCHEMA MODIFICATIONS - COUPONS
-- ============================================================================

-- Add constraints to coupons table
ALTER TABLE coupons
    DROP CONSTRAINT IF EXISTS check_used_count_non_negative;

ALTER TABLE coupons
    ADD CONSTRAINT check_used_count_non_negative
    CHECK (used_count >= 0);

ALTER TABLE coupons
    DROP CONSTRAINT IF EXISTS check_used_count_le_max_uses;

ALTER TABLE coupons
    ADD CONSTRAINT check_used_count_le_max_uses
    CHECK (max_uses IS NULL OR used_count <= max_uses);

-- Ensure used_count is not null
UPDATE coupons SET used_count = 0 WHERE used_count IS NULL;

ALTER TABLE coupons
    ALTER COLUMN used_count SET DEFAULT 0,
    ALTER COLUMN used_count SET NOT NULL;

RAISE NOTICE 'Applied coupons constraints';

-- ============================================================================
-- PHASE 4: SCHEMA MODIFICATIONS - ORDER_ITEMS
-- ============================================================================

-- Add constraints to order_items
ALTER TABLE order_items
    DROP CONSTRAINT IF EXISTS order_items_quantity_check;

ALTER TABLE order_items
    ADD CONSTRAINT order_items_quantity_check
    CHECK (quantity > 0);

ALTER TABLE order_items
    DROP CONSTRAINT IF EXISTS order_items_unit_price_cents_check;

ALTER TABLE order_items
    ADD CONSTRAINT order_items_unit_price_cents_check
    CHECK (unit_price_cents >= 0);

RAISE NOTICE 'Applied order_items constraints';

-- ============================================================================
-- PHASE 5: SCHEMA MODIFICATIONS - PRODUCT_CONTENTS
-- ============================================================================

-- Add UNIQUE constraint on product_contents.content (after cleanup)
DO $$
BEGIN
    -- Check if constraint already exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'product_contents_content_key'
    ) THEN
        ALTER TABLE product_contents
            ADD CONSTRAINT product_contents_content_key
            UNIQUE (content);
        RAISE NOTICE 'Added UNIQUE constraint on product_contents.content';
    ELSE
        RAISE NOTICE 'UNIQUE constraint on product_contents.content already exists';
    END IF;
END $$;

-- Add check constraint for used_at consistency
ALTER TABLE product_contents
    DROP CONSTRAINT IF EXISTS check_used_at_when_used;

ALTER TABLE product_contents
    ADD CONSTRAINT check_used_at_when_used
    CHECK (
        (is_used = FALSE AND used_at IS NULL AND used_by_order_id IS NULL) OR
        (is_used = TRUE AND used_at IS NOT NULL)
    );

RAISE NOTICE 'Applied product_contents constraints';

-- ============================================================================
-- PHASE 6: SCHEMA MODIFICATIONS - PAYMENTS
-- ============================================================================

-- Add constraints to payments
ALTER TABLE payments
    DROP CONSTRAINT IF EXISTS payments_amount_cents_check;

ALTER TABLE payments
    ADD CONSTRAINT payments_amount_cents_check
    CHECK (amount_cents >= 0);

ALTER TABLE payments
    DROP CONSTRAINT IF EXISTS payments_fee_cents_check;

ALTER TABLE payments
    ADD CONSTRAINT payments_fee_cents_check
    CHECK (fee_cents >= 0);

ALTER TABLE payments
    DROP CONSTRAINT IF EXISTS payments_total_payment_cents_check;

ALTER TABLE payments
    ADD CONSTRAINT payments_total_payment_cents_check
    CHECK (total_payment_cents >= 0);

RAISE NOTICE 'Applied payments constraints';

-- ============================================================================
-- PHASE 7: SCHEMA MODIFICATIONS - DEPOSITS
-- ============================================================================

-- Add missing columns to deposits if not exist
ALTER TABLE deposits
    ADD COLUMN IF NOT EXISTS gateway_order_id TEXT;

ALTER TABLE deposits
    ADD COLUMN IF NOT EXISTS fee_cents BIGINT DEFAULT 0;

ALTER TABLE deposits
    ADD COLUMN IF NOT EXISTS payable_cents BIGINT DEFAULT 0;

ALTER TABLE deposits
    ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;

ALTER TABLE deposits
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

ALTER TABLE deposits
    ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;

-- Update status enum to include new statuses
ALTER TABLE deposits
    DROP CONSTRAINT IF EXISTS deposits_status_check;

ALTER TABLE deposits
    ADD CONSTRAINT deposits_status_check
    CHECK (status IN ('pending', 'completed', 'failed', 'expired', 'cancelled'));

-- Add constraints to deposits
ALTER TABLE deposits
    DROP CONSTRAINT IF EXISTS deposits_amount_cents_check;

ALTER TABLE deposits
    ADD CONSTRAINT deposits_amount_cents_check
    CHECK (amount_cents > 0);

ALTER TABLE deposits
    DROP CONSTRAINT IF EXISTS deposits_fee_cents_check;

ALTER TABLE deposits
    ADD CONSTRAINT deposits_fee_cents_check
    CHECK (fee_cents >= 0);

ALTER TABLE deposits
    DROP CONSTRAINT IF EXISTS deposits_payable_cents_check;

ALTER TABLE deposits
    ADD CONSTRAINT deposits_payable_cents_check
    CHECK (payable_cents >= 0);

-- Add UNIQUE index on gateway_order_id (partial index, allows NULL)
DROP INDEX IF EXISTS deposits_gateway_order_id_idx;
CREATE UNIQUE INDEX deposits_gateway_order_id_idx
    ON deposits (gateway_order_id)
    WHERE gateway_order_id IS NOT NULL;

RAISE NOTICE 'Applied deposits constraints and indexes';

-- ============================================================================
-- PHASE 8: SCHEMA MODIFICATIONS - PRODUCT_TERM_SUBMISSIONS
-- ============================================================================

-- Add UNIQUE constraint on product_term_submissions (after cleanup)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'product_term_submissions_unique_submission'
    ) THEN
        ALTER TABLE product_term_submissions
            ADD CONSTRAINT product_term_submissions_unique_submission
            UNIQUE (order_id, product_id, telegram_user_id);
        RAISE NOTICE 'Added UNIQUE constraint on product_term_submissions';
    ELSE
        RAISE NOTICE 'UNIQUE constraint on product_term_submissions already exists';
    END IF;
END $$;

-- ============================================================================
-- PHASE 9: CREATE AUDIT_LOG TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    actor_id TEXT,
    action TEXT NOT NULL,
    details JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

RAISE NOTICE 'Created audit_log table';

-- ============================================================================
-- PHASE 10: CREATE ADDITIONAL INDEXES FOR PERFORMANCE
-- ============================================================================

-- Products indexes
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_active ON products(is_active) WHERE is_active = TRUE;

-- Orders indexes
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at DESC);

-- Order items indexes
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product ON order_items(product_id);

-- Product contents indexes
CREATE INDEX IF NOT EXISTS idx_product_contents_product ON product_contents(product_id);
CREATE INDEX IF NOT EXISTS idx_product_contents_unused ON product_contents(product_id, is_used) WHERE is_used = FALSE;
CREATE INDEX IF NOT EXISTS idx_product_contents_order ON product_contents(used_by_order_id) WHERE used_by_order_id IS NOT NULL;

-- Payments indexes
CREATE INDEX IF NOT EXISTS idx_payments_gateway ON payments(gateway_order_id);
CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(order_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);

-- Deposits indexes
CREATE INDEX IF NOT EXISTS idx_deposits_user ON deposits(user_id);
CREATE INDEX IF NOT EXISTS idx_deposits_status ON deposits(status);

-- Coupons indexes
CREATE INDEX IF NOT EXISTS idx_coupons_code ON coupons(code);
CREATE INDEX IF NOT EXISTS idx_coupons_valid ON coupons(valid_from, valid_until);

-- Term submissions indexes
CREATE INDEX IF NOT EXISTS idx_term_submissions_order ON product_term_submissions(order_id);

-- Term notifications indexes
CREATE INDEX IF NOT EXISTS idx_term_notifications_pending ON product_term_notifications(sent_at) WHERE sent_at IS NULL;

-- Audit log indexes
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_actor ON audit_log(actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);

RAISE NOTICE 'Created performance indexes';

-- ============================================================================
-- PHASE 11: DATA INTEGRITY CHECKS
-- ============================================================================

-- Check for orphaned order_items (products that don't exist)
DO $$
DECLARE
    orphan_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO orphan_count
    FROM order_items oi
    LEFT JOIN products p ON oi.product_id = p.id
    WHERE p.id IS NULL;

    IF orphan_count > 0 THEN
        RAISE WARNING 'Found % orphaned order_items with non-existent products', orphan_count;
    ELSE
        RAISE NOTICE 'No orphaned order_items found';
    END IF;
END $$;

-- Check for orphaned product_contents (products that don't exist)
DO $$
DECLARE
    orphan_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO orphan_count
    FROM product_contents pc
    LEFT JOIN products p ON pc.product_id = p.id
    WHERE p.id IS NULL;

    IF orphan_count > 0 THEN
        RAISE WARNING 'Found % orphaned product_contents with non-existent products', orphan_count;
    ELSE
        RAISE NOTICE 'No orphaned product_contents found';
    END IF;
END $$;

-- Recalculate product stock from product_contents
UPDATE products
SET stock = (
    SELECT COUNT(*) FROM product_contents
    WHERE product_contents.product_id = products.id
    AND is_used = FALSE
),
updated_at = NOW();

RAISE NOTICE 'Recalculated all product stock';

-- ============================================================================
-- PHASE 12: VALIDATION
-- ============================================================================

DO $$
DECLARE
    total_products INTEGER;
    total_contents INTEGER;
    total_orders INTEGER;
    total_deposits INTEGER;
BEGIN
    SELECT COUNT(*) INTO total_products FROM products;
    SELECT COUNT(*) INTO total_contents FROM product_contents;
    SELECT COUNT(*) INTO total_orders FROM orders;
    SELECT COUNT(*) INTO total_deposits FROM deposits;

    RAISE NOTICE 'Migration completed successfully!';
    RAISE NOTICE 'Database statistics:';
    RAISE NOTICE '  - Products: %', total_products;
    RAISE NOTICE '  - Product Contents: %', total_contents;
    RAISE NOTICE '  - Orders: %', total_orders;
    RAISE NOTICE '  - Deposits: %', total_deposits;
END $$;

-- ============================================================================
-- ROLLBACK SCRIPT (Run this if you need to undo changes)
-- ============================================================================
/*
-- To rollback this migration, run:

-- Drop new constraints
ALTER TABLE coupons DROP CONSTRAINT IF EXISTS check_used_count_non_negative;
ALTER TABLE coupons DROP CONSTRAINT IF EXISTS check_used_count_le_max_uses;
ALTER TABLE order_items DROP CONSTRAINT IF EXISTS order_items_quantity_check;
ALTER TABLE order_items DROP CONSTRAINT IF EXISTS order_items_unit_price_cents_check;
ALTER TABLE product_contents DROP CONSTRAINT IF EXISTS product_contents_content_key;
ALTER TABLE product_contents DROP CONSTRAINT IF EXISTS check_used_at_when_used;
ALTER TABLE payments DROP CONSTRAINT IF EXISTS payments_amount_cents_check;
ALTER TABLE payments DROP CONSTRAINT IF EXISTS payments_fee_cents_check;
ALTER TABLE payments DROP CONSTRAINT IF EXISTS payments_total_payment_cents_check;
ALTER TABLE deposits DROP CONSTRAINT IF EXISTS deposits_status_check;
ALTER TABLE deposits DROP CONSTRAINT IF EXISTS deposits_amount_cents_check;
ALTER TABLE deposits DROP CONSTRAINT IF EXISTS deposits_fee_cents_check;
ALTER TABLE deposits DROP CONSTRAINT IF EXISTS deposits_payable_cents_check;
ALTER TABLE product_term_submissions DROP CONSTRAINT IF EXISTS product_term_submissions_unique_submission;

-- Drop new indexes
DROP INDEX IF EXISTS deposits_gateway_order_id_idx;
DROP INDEX IF EXISTS idx_products_active;
DROP INDEX IF EXISTS idx_orders_status;
DROP INDEX IF EXISTS idx_orders_created;
DROP INDEX IF EXISTS idx_order_items_order;
DROP INDEX IF EXISTS idx_order_items_product;
DROP INDEX IF EXISTS idx_product_contents_order;
DROP INDEX IF EXISTS idx_payments_order;
DROP INDEX IF EXISTS idx_payments_status;
DROP INDEX IF EXISTS idx_deposits_user;
DROP INDEX IF EXISTS idx_deposits_status;
DROP INDEX IF EXISTS idx_coupons_code;
DROP INDEX IF EXISTS idx_coupons_valid;
DROP INDEX IF EXISTS idx_term_submissions_order;
DROP INDEX IF EXISTS idx_term_notifications_pending;
DROP INDEX IF EXISTS idx_audit_log_timestamp;
DROP INDEX IF EXISTS idx_audit_log_actor;
DROP INDEX IF EXISTS idx_audit_log_action;

-- Drop audit_log table
DROP TABLE IF EXISTS audit_log;

-- Restore from backup (if you created backups)
-- TRUNCATE product_contents;
-- INSERT INTO product_contents SELECT * FROM product_contents_backup_20250106;
-- ... etc for other tables

*/
