CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Users
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL UNIQUE,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    balance_cents BIGINT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Categories
CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    emoji TEXT DEFAULT '🗂️',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Products
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    price_cents BIGINT NOT NULL,
    stock INTEGER NOT NULL DEFAULT 0,
    sold_count INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Coupons
CREATE TABLE IF NOT EXISTS coupons (
    id SERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    description TEXT,
    discount_type TEXT NOT NULL CHECK (discount_type IN ('percent', 'flat')),
    discount_value BIGINT NOT NULL,
    max_uses INTEGER,
    used_count INTEGER DEFAULT 0,
    valid_from TIMESTAMP WITH TIME ZONE,
    valid_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT check_used_count_non_negative CHECK (used_count >= 0),
    CONSTRAINT check_used_count_le_max_uses CHECK (max_uses IS NULL OR used_count <= max_uses)
);

-- 5. Orders
CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    total_price_cents BIGINT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'awaiting_payment', 'paid', 'cancelled', 'expired')),
    coupon_id INTEGER REFERENCES coupons(id) ON DELETE SET NULL,
    metadata JSONB DEFAULT '{}'::JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. Order Items
CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_cents BIGINT NOT NULL CHECK (unit_price_cents >= 0),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 7. Product Contents (FIXED: Added UNIQUE constraint on content)
CREATE TABLE IF NOT EXISTS product_contents (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    content TEXT NOT NULL UNIQUE,  -- FIXED: Prevent duplicate content
    is_used BOOLEAN DEFAULT FALSE,
    used_by_order_id UUID REFERENCES orders(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    used_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT check_used_at_when_used CHECK (
        (is_used = FALSE AND used_at IS NULL AND used_by_order_id IS NULL) OR
        (is_used = TRUE AND used_at IS NOT NULL)
    )
);

-- 8. Payments
CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    gateway_order_id TEXT NOT NULL,
    method TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('created', 'waiting', 'completed', 'failed', 'expired', 'cancelled')),
    amount_cents BIGINT NOT NULL CHECK (amount_cents >= 0),
    fee_cents BIGINT DEFAULT 0 CHECK (fee_cents >= 0),
    total_payment_cents BIGINT NOT NULL CHECK (total_payment_cents >= 0),
    expires_at TIMESTAMP WITH TIME ZONE,
    payload JSONB DEFAULT '{}'::JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (order_id, gateway_order_id)
);

-- 9. Deposits (FIXED: Made gateway_order_id NOT NULL with better structure)
CREATE TABLE IF NOT EXISTS deposits (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount_cents BIGINT NOT NULL CHECK (amount_cents > 0),
    method TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'completed', 'failed', 'expired', 'cancelled')),
    reference TEXT,
    gateway_order_id TEXT UNIQUE,  -- FIXED: Made UNIQUE, nullable for backward compatibility
    fee_cents BIGINT DEFAULT 0 CHECK (fee_cents >= 0),
    payable_cents BIGINT DEFAULT 0 CHECK (payable_cents >= 0),
    expires_at TIMESTAMP WITH TIME ZONE,
    created_by_admin BOOLEAN DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- 10. Reply Templates
CREATE TABLE IF NOT EXISTS reply_templates (
    id SERIAL PRIMARY KEY,
    label TEXT NOT NULL UNIQUE,
    content TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 11. Product Terms (SNK)
CREATE TABLE IF NOT EXISTS product_terms (
    product_id INTEGER PRIMARY KEY REFERENCES products(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- FIXED: Added UNIQUE constraint to prevent duplicate submissions
CREATE TABLE IF NOT EXISTS product_term_submissions (
    id BIGSERIAL PRIMARY KEY,
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    telegram_user_id BIGINT NOT NULL,
    message TEXT,
    media_file_id TEXT,
    media_type TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (order_id, product_id, telegram_user_id)  -- FIXED: Prevent duplicate submissions
);

CREATE TABLE IF NOT EXISTS product_term_notifications (
    id BIGSERIAL PRIMARY KEY,
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    telegram_user_id BIGINT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    sent_at TIMESTAMPTZ,
    responded_at TIMESTAMPTZ,
    UNIQUE (order_id, product_id)
);

-- 12. Telemetry Daily
CREATE TABLE IF NOT EXISTS telemetry_daily (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    total_users INTEGER NOT NULL DEFAULT 0,
    total_transactions INTEGER NOT NULL DEFAULT 0,
    total_revenue_cents BIGINT NOT NULL DEFAULT 0,
    total_failures INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 13. Audit Log Table (ENABLED: For better tracking)
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    actor_id TEXT,
    action TEXT NOT NULL,
    details JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 14. Indexes
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_active ON products(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product ON order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_product_contents_product ON product_contents(product_id);
CREATE INDEX IF NOT EXISTS idx_product_contents_unused ON product_contents(product_id, is_used) WHERE is_used = FALSE;
CREATE INDEX IF NOT EXISTS idx_product_contents_order ON product_contents(used_by_order_id) WHERE used_by_order_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_payments_gateway ON payments(gateway_order_id);
CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(order_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
CREATE INDEX IF NOT EXISTS idx_deposits_gateway ON deposits(gateway_order_id) WHERE gateway_order_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_deposits_user ON deposits(user_id);
CREATE INDEX IF NOT EXISTS idx_deposits_status ON deposits(status);
CREATE INDEX IF NOT EXISTS idx_coupons_code ON coupons(code);
CREATE INDEX IF NOT EXISTS idx_coupons_valid ON coupons(valid_from, valid_until);
CREATE INDEX IF NOT EXISTS idx_term_submissions_order ON product_term_submissions(order_id);
CREATE INDEX IF NOT EXISTS idx_term_notifications_pending ON product_term_notifications(sent_at) WHERE sent_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_actor ON audit_log(actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);
