# 🚀 Quick Reference Guide – Bot Auto Order Telegram

**Version:** 0.7.0  
**Last Updated:** 2025-01-06  
**Status:** Production Ready

---

## 📌 Quick Links

- [Setup & Installation](#setup--installation)
- [Common Commands](#common-commands)
- [Environment Variables](#environment-variables-reference)
- [Admin Menu Navigation](#admin-menu-navigation)
- [Troubleshooting](#troubleshooting-quick-fixes)
- [Log Locations](#log-locations)
- [Database Queries](#useful-database-queries)
- [API Endpoints](#api-endpoints)

---

## Setup & Installation

### Fresh Install

```bash
# 1. Clone repository
git clone <repository-url>
cd bot-auto-order

# 2. Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Verify JobQueue
python -c "from telegram.ext import JobQueue; print('✅ JobQueue available!')"

# 5. Setup database
createdb bot_order
psql bot_order -f scripts/schema.sql

# 6. Configure environment
cp .env.example .env
nano .env  # Edit with your values

# 7. Run bot
python -m src.main --mode polling
```

### Update Existing Installation

```bash
# 1. Backup first!
python -m src.tools.backup_manager create --offsite

# 2. Pull latest code
git pull origin main

# 3. Update dependencies
pip install -r requirements.txt

# 4. Restart bot
pkill -f "python -m src.main"
python -m src.main --mode polling &
```

### Reinstall Dependencies (Fix JobQueue Warning)

```bash
source venv/bin/activate
pip uninstall python-telegram-bot -y
pip install -r requirements.txt
python -c "from telegram.ext import JobQueue; print('✅')"
```

---

## Common Commands

### Bot Operations

```bash
# Start bot (polling mode)
python -m src.main --mode polling

# Start bot (webhook mode)
python -m src.main --mode webhook

# Start bot (auto failover)
python -m src.main --mode auto

# Stop bot
pkill -f "python -m src.main"

# Restart bot
pkill -f "python -m src.main" && python -m src.main --mode polling &
```

### Health & Monitoring

```bash
# Run health check
python -m src.tools.healthcheck

# View logs (today)
tail -f logs/telegram-bot/$(date +%Y-%m-%d).log

# View logs (specific date)
tail -f logs/telegram-bot/2025-01-16.log

# View audit logs
ls -lh logs/audit/

# Check health check logs
tail -f logs/health-check/$(date +%Y-%m-%d).log
```

### Backup & Restore

```bash
# Create backup
python -m src.tools.backup_manager create

# Create backup with offsite
python -m src.tools.backup_manager create --offsite

# List backups
python -m src.tools.backup_manager list

# Restore from backup
python -m src.tools.backup_manager restore --backup-file backups/backup-2025-01-16.tar.gz

# Verify backup
python -m src.tools.backup_manager verify --backup-file backups/backup-2025-01-16.tar.gz
```

### Docker Operations

```bash
# Build image
docker build -t bot-auto-order:0.2.2 .

# Run with Docker Compose
docker compose up -d

# View logs
docker compose logs -f telegram-bot

# Restart services
docker compose restart

# Stop services
docker compose down

# Rebuild and restart
docker compose up -d --build
```

---

## Environment Variables Reference

### Required Variables

```bash
# Telegram Configuration
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz  # Bot token dari @BotFather
TELEGRAM_ADMIN_IDS=5473468582                              # Single admin atau 123,456,789
TELEGRAM_OWNER_IDS=341404536                               # Owner ID (optional)

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/bot_order

# Pakasir Integration
PAKASIR_PROJECT_SLUG=your-slug
PAKASIR_API_KEY=your-api-key
PAKASIR_PUBLIC_DOMAIN=https://pots.my.id
PAKASIR_WEBHOOK_SECRET=optional-webhook-secret

# Security
DATA_ENCRYPTION_KEY=<base64-key>  # Generate: openssl rand -base64 32
```

### Optional Variables

```bash
# General Settings
BOT_TIMEZONE=Asia/Jakarta
LOG_LEVEL=INFO
BOT_STORE_NAME=Bot Auto Order
TELEGRAM_MODE=polling  # or webhook or auto

# Features
ENABLE_OWNER_ALERTS=true
OWNER_ALERT_THRESHOLD=ERROR
OWNER_BOT_TOKEN=<optional-separate-bot-token>

# SNK Settings
SNK_RETENTION_DAYS=30
ENABLE_AUTO_SNK_DISPATCH=true

# Health Check
ENABLE_AUTO_HEALTHCHECK=true
HEALTHCHECK_INTERVAL_MINUTES=5

# Backup
ENABLE_AUTO_BACKUP=true
BACKUP_TIME=00:00
BACKUP_AUTOMATIC_OFFSITE=true
```

---

## Admin Menu Navigation

### Main Menu Structure

```
⚙️ Admin Settings
├── 📝 Kelola Respon Bot
│   ├── Preview Templates
│   ├── Edit Template Text
│   └── Upload Template Image
├── 📦 Kelola Produk
│   ├── List Products
│   ├── Create Product
│   ├── Edit Product
│   └── View Statistics
├── 📋 Kelola Order
│   ├── View Orders
│   ├── Filter by Status
│   └── Update Order Status
├── 👥 Kelola User
│   ├── User Statistics
│   ├── User List (paginated)
│   ├── Block/Unblock User
│   └── View User Details
├── 🎟️ Kelola Voucher
│   ├── Generate Voucher (Nominal)
│   ├── Generate Voucher (Percentage)
│   └── Generate Voucher (Custom)
├── 📢 Broadcast
│   ├── Send Text Message
│   └── Send Photo Message
├── 🧮 Calculator
│   ├── Refund Calculator
│   └── Deposit Calculator
├── 📊 Statistik
│   └── View Dashboard
└── 💰 Deposit
    └── Manage User Deposits
```

### Deposit QRIS (Customer Flow)
1. Customer tekan `💰 Deposit` → pilih `💳 Deposit QRIS`.
2. Input nominal minimal **Rp10.000** (angka saja).  
3. Bot menghitung fee otomatis **0,7% + Rp310**, menampilkan subtotal + fee + total dibayar, dan mengirim QR & tautan checkout.
4. Invoice aktif selama 5 menit; bila expired bot menghapus pesan lama dan mengirim info pembatalan.

### Access Shortcuts

| Feature | Access Method |
|---------|---------------|
| Admin Menu | Click `⚙️ Admin Settings` button (admin keyboard) |
| Calculator | `/refund_calculator` or `/set_calculator` command |
| Statistics | Admin Menu → 📊 Statistik |
| Broadcast | Admin Menu → 📢 Broadcast |
| User Management | Admin Menu → 👥 Kelola User |

---

## Troubleshooting Quick Fixes

### Bot Not Starting

**Symptom:** Bot fails to start or crashes immediately

```bash
# Check logs
tail -n 50 logs/telegram-bot/$(date +%Y-%m-%d).log

# Common fixes:
# 1. Invalid token
echo $TELEGRAM_BOT_TOKEN  # Verify token is set

# 2. Database connection
psql $DATABASE_URL -c "SELECT 1;"  # Test connection

# 3. Port already in use
sudo lsof -i :9000  # Check port 9000
sudo fuser -k 9000/tcp  # Kill process on port

# 4. Missing dependencies
pip install -r requirements.txt
```

### JobQueue Warning

**Symptom:** `PTBUserWarning: No 'JobQueue' set up`

```bash
# Fix: Reinstall with job-queue extra
pip uninstall python-telegram-bot -y
pip install -r requirements.txt

# Verify
python -c "from telegram.ext import JobQueue; print('✅ Fixed!')"
```

### Admin Keyboard Not Showing

**Symptom:** Admin user doesn't see `⚙️ Admin Settings` button

```bash
# Check admin IDs configuration
echo $TELEGRAM_ADMIN_IDS

# Valid formats:
# Single: TELEGRAM_ADMIN_IDS=5473468582
# Multiple: TELEGRAM_ADMIN_IDS=5473468582,123456789

# Get your Telegram ID
# Send /start to @userinfobot

# Restart bot after fixing .env
pkill -f "python -m src.main"
python -m src.main --mode polling &
```

### User Statistics Not Counting

**Symptom:** Shows 0 users despite people starting bot

```bash
# Fixed in v0.2.2 - update to latest version
git pull origin main
pip install -r requirements.txt

# Verify fix
psql $DATABASE_URL -c "SELECT COUNT(*) FROM users;"

# Should increment after each new /start
```

### Payment Webhook Not Working

**Symptom:** Payments don't update order status

```bash
# Check webhook endpoint
curl -X POST http://your-domain.com/webhooks/pakasir \
  -H "Content-Type: application/json" \
  -d '{"test": "true"}'

# Check logs for webhook requests
grep "webhook" logs/telegram-bot/$(date +%Y-%m-%d).log

# Verify Pakasir configuration
echo $PAKASIR_WEBHOOK_SECRET
echo $PAKASIR_PUBLIC_DOMAIN
```

### Database Connection Lost

**Symptom:** Bot logs show database errors

```bash
# Test connection
psql $DATABASE_URL -c "SELECT NOW();"

# Reconnect
# Bot should auto-reconnect; if not, restart:
pkill -f "python -m src.main"
python -m src.main --mode polling &

# Check connection pool
psql $DATABASE_URL -c "SELECT count(*) FROM pg_stat_activity;"
```

### Broadcast Fails

**Symptom:** Broadcast doesn't send to all users

```bash
# Check logs
grep "broadcast" logs/telegram-bot/$(date +%Y-%m-%d).log

# Common causes:
# 1. Users blocked bot (automatic skip)
# 2. Rate limiting (adjust if needed)
# 3. Database connection (see above)

# Check blocked users
psql $DATABASE_URL -c "SELECT COUNT(*) FROM users WHERE blocked = true;"
```

---

## Log Locations

### Log Directory Structure

```
logs/
├── telegram-bot/
│   ├── 2025-01-16.log      # Daily bot logs
│   ├── 2025-01-15.log
│   └── ...
├── audit/
│   ├── config_changes.log  # Admin config changes
│   ├── user_actions.log    # Admin actions
│   └── ...
├── health-check/
│   ├── 2025-01-16.log      # Health check results
│   └── ...
└── maintenance/
    ├── backup.log          # Backup operations
    └── restore.log         # Restore operations
```

### Log Format

```
[YYYY-MM-DD HH:MM:SS] [LEVEL] message

Examples:
[2025-01-16 10:00:00] [INFO] Bot initialization successful
[2025-01-16 10:00:05] [SUCCESS] User 5473468582 started bot - role: admin
[2025-01-16 10:00:10] [ERROR] API Pakasir timeout, fallback active
[2025-01-16 10:00:15] [ADMIN] Admin 5473468582 accessed Admin Settings
```

### Useful Log Commands

```bash
# View logs in real-time
tail -f logs/telegram-bot/$(date +%Y-%m-%d).log

# View last 100 lines
tail -n 100 logs/telegram-bot/$(date +%Y-%m-%d).log

# Search for errors
grep "ERROR" logs/telegram-bot/$(date +%Y-%m-%d).log

# Search for admin actions
grep "ADMIN" logs/telegram-bot/$(date +%Y-%m-%d).log

# Count errors today
grep -c "ERROR" logs/telegram-bot/$(date +%Y-%m-%d).log

# View audit logs
cat logs/audit/config_changes.log
```

---

## Useful Database Queries

### Check Data Integrity (v0.7.0+)

```sql
-- Check for duplicate product contents (should be 0)
SELECT content, COUNT(*) as cnt 
FROM product_contents 
GROUP BY content 
HAVING COUNT(*) > 1;

-- Check stock consistency
SELECT p.id, p.code, p.name, p.stock as recorded_stock,
       COUNT(pc.id) FILTER (WHERE pc.is_used = FALSE) as actual_stock
FROM products p
LEFT JOIN product_contents pc ON pc.product_id = p.id
GROUP BY p.id, p.code, p.name, p.stock
HAVING p.stock != COUNT(pc.id) FILTER (WHERE pc.is_used = FALSE);

-- Check orphaned order items
SELECT oi.id, oi.product_id
FROM order_items oi
LEFT JOIN products p ON oi.product_id = p.id
WHERE p.id IS NULL;

-- Check voucher usage
SELECT code, used_count, max_uses,
       CASE WHEN max_uses IS NULL THEN NULL
            ELSE ROUND((used_count::NUMERIC / max_uses::NUMERIC) * 100, 2)
       END as usage_percentage
FROM coupons
ORDER BY used_count DESC;
```

### User Statistics

```sql
-- Total users
SELECT COUNT(*) FROM users;

-- Active users (not blocked)
SELECT COUNT(*) FROM users WHERE blocked = false;

-- New users today
SELECT COUNT(*) FROM users WHERE created_at::date = CURRENT_DATE;

-- Top users by orders
SELECT u.telegram_id, u.username, COUNT(o.id) as order_count
FROM users u
LEFT JOIN orders o ON u.telegram_id = o.user_telegram_id
GROUP BY u.telegram_id, u.username
ORDER BY order_count DESC
LIMIT 10;
```

### Order Statistics

```sql
-- Total orders
SELECT COUNT(*) FROM orders;

-- Orders by status
SELECT status, COUNT(*) 
FROM orders 
GROUP BY status;

-- Revenue today
SELECT SUM(total_amount) 
FROM orders 
WHERE created_at::date = CURRENT_DATE 
AND status = 'paid';

-- Recent orders
SELECT id, user_telegram_id, total_amount, status, created_at
FROM orders
ORDER BY created_at DESC
LIMIT 20;
```

### Product Statistics

```sql
-- Total products
SELECT COUNT(*) FROM products;

-- Low stock products
SELECT name, stock 
FROM products 
WHERE stock <= 3 
AND active = true;

-- Best selling products
SELECT p.name, COUNT(oi.id) as sales
FROM products p
LEFT JOIN order_items oi ON p.id = oi.product_id
GROUP BY p.name
ORDER BY sales DESC
LIMIT 10;
```

### Broadcast Statistics

```sql
-- Recent broadcasts
SELECT id, message, total_users, success_count, failed_count, created_at
FROM broadcast_jobs
ORDER BY created_at DESC
LIMIT 10;

-- Broadcast success rate
SELECT 
  AVG(success_count::float / NULLIF(total_users, 0) * 100) as avg_success_rate
FROM broadcast_jobs
WHERE created_at >= CURRENT_DATE - INTERVAL '7 days';
```

---

## API Endpoints

### Webhook Endpoints

```
POST /webhooks/pakasir
- Receives payment notifications from Pakasir
- Requires: PAKASIR_WEBHOOK_SECRET (optional)
- Payload: Pakasir webhook format
```

### Health Check (if exposed)

```
GET /health
- Returns: {"status": "healthy", "timestamp": "..."}
```

### Internal Tools

```bash
# Health check CLI
python -m src.tools.healthcheck

# Backup manager CLI
python -m src.tools.backup_manager <command>
```

---

## Configuration Files

### Important Files

| File | Purpose | Location |
|------|---------|----------|
| `.env` | Environment variables | Root directory |
| `requirements.txt` | Python dependencies | Root directory |
| `scripts/schema.sql` | Database schema | `scripts/` |
| `README.md` | Main documentation | Root directory |
| `docker-compose.yml` | Docker orchestration | Root directory (if using Docker) |

### Config Priority

1. Environment variables (`.env`)
2. System environment variables
3. Default values in code

---

## Performance Tips

### Optimize Database

```sql
-- Analyze tables
ANALYZE users;
ANALYZE orders;
ANALYZE products;

-- Check slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Vacuum database
VACUUM ANALYZE;
```

### Monitor Memory

```bash
# Check bot memory usage
ps aux | grep "python -m src.main"

# Monitor system memory
free -h

# Check disk space
df -h
```

### Rate Limiting

```python
# In code, adjust rate limits if needed
# File: src/bot/handlers.py
# Look for rate limiting configurations
```

---

## Security Checklist

- [ ] `TELEGRAM_BOT_TOKEN` kept secret
- [ ] `DATABASE_URL` not exposed in logs
- [ ] `PAKASIR_API_KEY` not exposed
- [ ] `DATA_ENCRYPTION_KEY` generated and secure
- [ ] Admin IDs verified and correct
- [ ] Webhook secret configured (if using webhooks)
- [ ] SSL/TLS enabled for webhooks
- [ ] Firewall rules configured
- [ ] Database backups encrypted
- [ ] Log files secured (no sensitive data)

---

## Common Workflows

### Adding New Admin

```bash
# 1. Get Telegram ID
# User sends /start to @userinfobot

# 2. Update .env
nano .env
# Add ID to TELEGRAM_ADMIN_IDS (comma-separated if multiple)
# Example: TELEGRAM_ADMIN_IDS=5473468582,987654321

# 3. Restart bot
pkill -f "python -m src.main"
python -m src.main --mode polling &

# 4. Verify
# New admin sends /start and checks for ⚙️ Admin Settings button
```

### Creating Product

```
1. Admin sends /start
2. Click ⚙️ Admin Settings
3. Click 📦 Kelola Produk
4. Follow prompts to create product
5. Set name, price, stock, category
6. Confirm creation
```

### Sending Broadcast

```
1. Admin sends /start
2. Click ⚙️ Admin Settings
3. Click 📢 Broadcast
4. Choose text or photo
5. Input message/upload photo
6. Confirm send
7. Monitor real-time statistics
8. (Optional) Click ❌ Cancel to abort
```

### Manual Backup

```bash
# 1. Create backup
python -m src.tools.backup_manager create --offsite

# 2. Verify backup
ls -lh backups/

# 3. Test restore (staging only!)
python -m src.tools.backup_manager restore --backup-file backups/latest.tar.gz

# 4. Document backup location
echo "Backup stored at: backups/backup-$(date +%Y-%m-%d).tar.gz"
```

---

## Getting Help

### Documentation

- **Main README:** `README.md`
- **Changelog:** `docs/CHANGELOG.md`
- **Testing Guide:** `docs/TESTING_CHECKLIST.md`
- **Implementation Report:** `docs/IMPLEMENTATION_REPORT.md`
- **Core Summary:** `docs/core_summary.md`
- **PRD:** `docs/02_prd.md`

### Debugging Steps

1. Check logs: `tail -f logs/telegram-bot/$(date +%Y-%m-%d).log`
2. Verify configuration: `env | grep TELEGRAM`
3. Test database: `psql $DATABASE_URL -c "SELECT 1;"`
4. Run health check: `python -m src.tools.healthcheck`
5. Consult troubleshooting section above
6. Check recent changes: `git log --oneline -10`

### Support Channels

- **Documentation:** `/docs` directory
- **Logs:** `/logs` directory
- **Repository:** Check repository issues/PRs
- **Admin Contact:** Configure via `TELEGRAM_OWNER_IDS`

---

## Version History Quick Reference

| Version | Date | Key Changes |
|---------|------|-------------|
| 0.2.2 | 2025-01-16 | Admin menu overhaul, role-based keyboard, HTML formatting |
| 0.2.1 | 2025-01-15 | Config fixes, JobQueue support, user tracking |
| 0.2.0 | 2025-06-01 | Health checks, backup automation |
| 0.1.0 | 2025-05-01 | Initial release |

---

## Emergency Contacts

**System Owner:** [Configure in TELEGRAM_OWNER_IDS]  
**Technical Support:** [Your support channel]  
**Documentation:** `/docs` directory  
**Logs:** `/logs` directory

---

**Last Updated:** 2025-01-16  
**Document Version:** 1.0  
**Bot Version:** 0.2.2

---

💡 **Tip:** Bookmark this page for quick access during operations and troubleshooting!
