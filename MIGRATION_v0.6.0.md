# Migration Guide v0.6.0 - Product Content System

## Overview

Version 0.6.0 introduces a **product content-based inventory system** yang mengubah cara stok dikelola. Sebelumnya, stok adalah angka manual yang bisa dimanipulasi. Sekarang, **stok = jumlah content digital yang tersedia** di database.

### Breaking Changes

⚠️ **PERHATIAN:** Update ini mengubah fundamental cara kerja stok produk!

1. **Stock Management:** Stok tidak lagi bisa diset manual. Stok = COUNT(unused product_contents)
2. **Database Schema:** Tabel baru `product_contents` ditambahkan
3. **Payment Flow:** Saat bayar, sistem alokasikan content ke order, bukan hanya kurangi angka stok
4. **Fee Calculation:** Fix double fee calculation dengan Pakasir QRIS

---

## Major Changes Summary

### 1. ✅ CRITICAL FIX: QRIS Fee Calculation
**Problem:** Fee dihitung 2x (sistem + Pakasir) → Harga tidak cocok
**Solution:** Sistem hanya hitung fee untuk display, kirim subtotal saja ke Pakasir

### 2. ✅ Product Content System (NEW)
**Feature:** Sistem inventory berbasis content digital
- Admin upload content (email, password, code, dll) untuk setiap unit produk
- Stok otomatis = jumlah content yang belum dipakai
- Saat customer bayar, dapat content asli (bukan notifikasi kosong)

### 3. ✅ Enhanced Admin Notifications
**Feature:** Notifikasi lebih lengkap untuk admin
- Status pembayaran (pending/success)
- Notifikasi saat deposit berhasil
- Detail lengkap customer dan produk

### 4. ✅ Improved UX
- Welcome message dengan inline keyboard (INFORMASI & Cara Order)
- Product list dengan horizontal button layout
- Remove generic error untuk pesan tidak dikenal
- Replace "Pakasir" → "Biaya Layanan" di semua tempat

---

## Migration Steps

### Step 1: Backup Database

```bash
# Backup database sebelum migration
pg_dump -h localhost -U postgres -d bot_order > backup_pre_v0.6.0.sql

# Atau gunakan backup manager built-in
docker exec bot-container python -m src.tools.backup_manager create
```

### Step 2: Update Database Schema

```sql
-- Run migration script
-- File: scripts/schema.sql (new lines)

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
CREATE INDEX IF NOT EXISTS idx_product_contents_unused ON product_contents(product_id, is_used) 
    WHERE is_used = FALSE;
```

### Step 3: Migrate Existing Products

Ada 3 opsi untuk handle existing products:

#### Option A: Reset All Stock (RECOMMENDED)

Paling aman - mulai fresh dengan content-based system.

```sql
-- Set semua stok jadi 0
UPDATE products SET stock = 0;

-- Admin harus input content baru untuk semua produk
-- Menggunakan menu admin di bot
```

**Pros:** Clean, no data inconsistency
**Cons:** Admin harus input ulang semua content

#### Option B: Generate Dummy Content

Cepat tapi tidak ada real content untuk customer.

```sql
-- Generate dummy content untuk existing stock
INSERT INTO product_contents (product_id, content, is_used)
SELECT 
    id as product_id,
    'PLACEHOLDER - Admin belum update content untuk produk ini. Segera hubungi admin!' as content,
    FALSE
FROM products p
CROSS JOIN generate_series(1, p.stock) gs
WHERE p.stock > 0;

-- Recalculate stock (should be same as before)
UPDATE products
SET stock = (
    SELECT COUNT(*) FROM product_contents
    WHERE product_contents.product_id = products.id
    AND is_used = FALSE
);
```

**Pros:** Quick migration, stock preserved
**Cons:** Customer dapat placeholder text, bukan real content

#### Option C: Manual Content Entry (BEST for Small Inventory)

Admin input content manual untuk produk penting.

```sql
-- Keep stock, tapi admin harus input content sebelum bisa jual
-- Temporary: prevent checkout untuk produk tanpa content

-- Add constraint (optional)
-- Ini akan error jika ada order untuk produk tanpa content
-- Admin HARUS input content dulu
```

### Step 4: Deploy Updated Code

```bash
# Pull latest code
cd /path/to/bot-auto-order
git pull origin main

# Rebuild Docker image
docker build -t bot-auto-order:v0.6.0 .

# Stop existing container
docker-compose down

# Start with new version
docker-compose up -d

# Check logs
docker-compose logs -f bot
```

### Step 5: Verify Migration

```bash
# Connect to database
psql -h localhost -U postgres -d bot_order

# Check product_contents table exists
\dt product_contents

# Check indexes
\di idx_product_contents_*

# Verify stock consistency
SELECT 
    p.id,
    p.name,
    p.stock,
    COUNT(pc.id) FILTER (WHERE pc.is_used = FALSE) as actual_content_count
FROM products p
LEFT JOIN product_contents pc ON pc.product_id = p.id
GROUP BY p.id, p.name, p.stock
HAVING p.stock != COUNT(pc.id) FILTER (WHERE pc.is_used = FALSE);

-- Should return 0 rows (no inconsistency)
```

---

## Admin Training: How to Use New System

### Adding Product Content (Stok Baru)

**OLD WAY (v0.5.0):**
```
Admin Settings → Kelola Produk → Edit Produk → Set stock = 10
```

**NEW WAY (v0.6.0):**
```
Admin Settings → Kelola Produk → Kelola Stok → Pilih Produk → Input Content

Format content (contoh):
===========================
NETFLIX 1 BULAN PREMIUM

Email: user123@gmail.com
Password: Pass@word123

WAJIB KIRIM SCREENSHOT LOGIN MAKS 1X24 JAM!
Garansi hangus jika tidak screenshot.
===========================

Ulangi untuk setiap unit stok yang mau ditambah.
```

### Checking Stock

```
Admin Settings → Overview → Product Overview

Stok yang ditampilkan = content yang belum terpakai
Real-time, tidak bisa manipulasi manual
```

### When Customer Buys

**OLD WAY:**
- Stock -= 1 (number only)
- Customer dapat notifikasi "Pembayaran berhasil" (no product data)
- Admin harus kirim manual via chat

**NEW WAY:**
- System allocate 1 content → mark as used
- Stock otomatis -= 1
- Customer **langsung dapat content** dalam format yang sudah admin set
- Admin dapat notifikasi "Pembayaran Berhasil + detail customer"

---

## Testing Checklist

### Pre-Production Testing

- [ ] Create test product dengan 3 content
- [ ] Verify stock = 3
- [ ] Buy product → Pay → Verify customer receive content
- [ ] Verify stock = 2 after purchase
- [ ] Check content marked as used in DB
- [ ] Delete 1 unused content → Verify stock = 1
- [ ] Test QRIS payment → Verify amount matches invoice
- [ ] Test deposit → Verify amount matches invoice
- [ ] Wait 5 min on unpaid invoice → Verify auto-cancel works

### Production Smoke Test

- [ ] Send /start → Check welcome message has inline keyboard
- [ ] Open product list → Check horizontal button layout
- [ ] Try random text → Should not get "sistem sibuk" error
- [ ] Check admin notifications include status
- [ ] Test full purchase flow end-to-end

---

## Rollback Plan

Jika ada masalah critical:

### Quick Rollback to v0.5.0

```bash
# Stop current version
docker-compose down

# Restore database backup
psql -h localhost -U postgres -d bot_order < backup_pre_v0.6.0.sql

# Deploy old version
git checkout v0.5.0
docker build -t bot-auto-order:v0.5.0 .
docker-compose up -d
```

### Partial Rollback (Keep Schema, Revert Code Only)

```bash
# If schema is fine but code has issues
git revert <commit-hash>
docker build -t bot-auto-order:v0.5.1-hotfix .
docker-compose up -d

# Product contents table will remain but not used
# Can migrate forward later
```

---

## Performance Considerations

### Database Impact

**New Queries:**
- `SELECT COUNT(*) FROM product_contents WHERE product_id = ? AND is_used = FALSE`
- `UPDATE product_contents SET is_used = TRUE WHERE id IN (...)`

**Indexes Added:**
- `idx_product_contents_product` on `(product_id)`
- `idx_product_contents_unused` on `(product_id, is_used)` WHERE is_used = FALSE

**Expected Performance:**
- Stock check: <5ms (indexed)
- Content allocation: <10ms per unit (with FOR UPDATE SKIP LOCKED)
- No significant impact on existing queries

### Storage Impact

**Estimate:**
- 1 product content = ~500 bytes average (text data)
- 1000 products × 10 stock each = 10,000 rows = ~5 MB
- Negligible storage impact for typical use case

---

## API Changes

### New Functions in `src/services/product_content/`

```python
# Add content for product
await add_product_content(product_id: int, content: str) -> int

# Get available content for purchase
await get_available_content(product_id: int, quantity: int) -> List[Dict]

# Mark content as used by order
await mark_content_as_used(content_id: int, order_id: UUID) -> bool

# Get content count (for stock display)
await get_content_count(product_id: int) -> int

# List all content for product
await list_product_contents(product_id: int, include_used: bool, limit: int) -> List[Dict]

# Get contents delivered to order
await get_order_contents(order_id: UUID) -> List[Dict]

# Recalculate all stock (maintenance)
await recalculate_all_stock() -> None
```

### Modified Functions

**Payment Service:**
```python
# Now allocates content instead of just decrementing stock
await payment_service.mark_payment_completed(gateway_order_id, amount_cents)
```

**Product Service:**
```python
# Stock is now read-only from app perspective
# Calculated from: SELECT COUNT(*) FROM product_contents WHERE is_used = FALSE
product.stock  # Auto-synced with content count
```

---

## Troubleshooting

### Issue: Stock shows 0 but there are unused contents

**Cause:** Stock calculation out of sync

**Fix:**
```python
# Run from Python console or create admin command
from src.services.product_content import recalculate_all_stock
await recalculate_all_stock()
```

### Issue: Customer didn't receive product content after payment

**Check:**
1. Order status = 'paid'?
2. Content exists in `product_contents` with `used_by_order_id = <order_id>`?
3. Check bot logs for delivery errors
4. Check customer's telegram_id is correct

**Manual Send:**
```python
from src.services.product_content import get_order_contents
contents = await get_order_contents(order_id)
# Send manually via bot to customer
```

### Issue: QRIS amount still mismatch

**Check:**
1. Clear cache/restart bot
2. Check Pakasir API response in logs
3. Verify `calculate_gateway_fee()` not being added to API request
4. Check `build_payment_url()` uses `total_cents` not `payable_cents`

### Issue: Expired invoice not auto-deleted after 5 minutes

**Check:**
1. `check_expired_payments_job` running? Check logs
2. `expires_at` field populated in database?
3. Timezone settings correct? (BOT_TIMEZONE=Asia/Jakarta)
4. Check `src/core/tasks.py` for errors

---

## FAQ

### Q: Apa yang terjadi dengan produk lama yang sudah ada stok?

**A:** Tergantung opsi migration yang dipilih:
- Option A: Stok jadi 0, admin input ulang
- Option B: Generate dummy content (placeholder text)
- Option C: Keep stok, tapi admin harus input content sebelum bisa jual

### Q: Bisakah admin edit content yang sudah ada?

**A:** Ya, bisa via admin menu "Kelola Stok" → "Edit Content". Tapi jika sudah terpakai (is_used = TRUE), tidak bisa diedit (sudah dikirim ke customer).

### Q: Bagaimana jika stok habis di tengah transaksi?

**A:** System menggunakan `FOR UPDATE SKIP LOCKED` untuk prevent race condition. Jika content tidak cukup:
1. Checkout akan gagal jika validasi di awal
2. Atau jika lolos checkout, customer dapat partial content + log error

**Recommendation:** Tambah validasi di checkout untuk cek stock availability sebelum create order.

### Q: Apakah ada limit untuk content size?

**A:** Database column type = TEXT (unlimited praktis). Tapi untuk UX, recommended max ~2000 characters per content. Jika lebih panjang, pertimbangkan kirim sebagai file.

### Q: Bagaimana cara backup product contents?

**A:** Same as database backup:
```bash
pg_dump -t product_contents -h localhost -U postgres -d bot_order > contents_backup.sql
```

### Q: Bisakah 1 product punya multiple format content?

**A:** Bisa, tapi harus manual diatur. Setiap row di `product_contents` adalah 1 unit. Admin bisa input format berbeda untuk produk yang sama (misal: beberapa akun shared, beberapa private).

---

## Support & Contact

**Issue Tracker:** https://github.com/your-repo/bot-auto-order/issues  
**Documentation:** `/docs/` folder in repository  
**Admin Manual:** `/docs/admin_guide.md` (to be created)

---

## Changelog

### v0.6.0 (2025-01-XX)

**Critical Fixes:**
- ✅ Fix QRIS double fee calculation (invoice vs actual payment mismatch)
- ✅ Remove generic error spam for unrecognized messages

**New Features:**
- ✅ Product content-based inventory system
- ✅ Auto-delivery of digital products to customers
- ✅ Enhanced admin notifications (status + success alerts)
- ✅ Welcome message with inline keyboard
- ✅ Horizontal product selection layout

**Improvements:**
- ✅ Replace "Pakasir" with "Biaya Layanan" everywhere
- ✅ Better expired invoice handling (already implemented, verified)
- ✅ Product content service with full CRUD operations
- ✅ Auto-sync stock with content availability

**Database:**
- ✅ New table: `product_contents`
- ✅ New indexes: `idx_product_contents_product`, `idx_product_contents_unused`

**API Changes:**
- ✅ New service: `src/services/product_content`
- ✅ Modified: `PaymentService.mark_payment_completed()` - now allocates content
- ✅ Modified: Product stock calculation - now read-only, content-based

---

**Migration Date:** _______________  
**Performed By:** _______________  
**Success:** [ ] Yes [ ] No [ ] Partial  
**Issues Encountered:** _______________________________________________  
**Rollback Required:** [ ] Yes [ ] No  

---

*End of Migration Guide v0.6.0*