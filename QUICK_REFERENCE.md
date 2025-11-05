# 🚀 Quick Reference Card - Bot Auto Order

**Version:** 0.2.1+  
**Last Updated:** 2025-01-15

---

## 📋 Quick Start

### Local Development
```bash
# Setup environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env dengan token dan credentials

# Run database setup
createdb bot_order
psql bot_order -f scripts/schema.sql

# Start bot (polling mode)
python -m src.main --mode polling
```

### Docker Deployment
```bash
# Build image
docker build -t bot-auto-order:0.2.1+ .

# Tag and push (optional)
docker tag bot-auto-order:0.2.1+ username/bot-auto-order:0.2.1+
docker push username/bot-auto-order:0.2.1+

# Run with compose
cd deployments/bot-mystore-qris
./run.sh
```

---

## 🔧 Common Operations

### Check Bot Status
```bash
# Check running processes
ps aux | grep python | grep src.main

# Check Docker containers
docker ps | grep bot-auto-order

# Check logs
tail -f logs/telegram-bot/$(date +%Y-%m-%d).log
```

### Restart Services
```bash
# Restart bot (polling)
pkill -f "python -m src.main"
python -m src.main --mode polling &

# Restart webhook server
sudo fuser -k 9000/tcp
python -m src.server --host 0.0.0.0 --port 9000 &

# Restart Docker container
docker compose restart
```

### Port Management
```bash
# Check what's using a port
sudo lsof -i :8080
sudo lsof -i :9000

# Kill process on port
sudo fuser -k 8080/tcp
sudo fuser -k 9000/tcp

# Check if port is listening
netstat -tuln | grep 8080
netstat -tuln | grep 9000
```

---

## 🐛 Troubleshooting

### Bot Not Responding
```bash
# 1. Check if process is running
ps aux | grep src.main

# 2. Check logs for errors
tail -n 100 logs/telegram-bot/$(date +%Y-%m-%d).log

# 3. Test bot token
curl https://api.telegram.org/bot<TOKEN>/getMe

# 4. Restart in debug mode
LOG_LEVEL=DEBUG python -m src.main --mode polling
```

### Admin Can't Login
```bash
# Check .env configuration
cat .env | grep TELEGRAM_ADMIN_IDS
cat .env | grep TELEGRAM_OWNER_IDS

# Format harus benar (tanpa spasi, tanpa quotes):
# TELEGRAM_ADMIN_IDS=5473468582
# atau untuk multiple:
# TELEGRAM_ADMIN_IDS=5473468582,123456789
```

### Database Connection Issues
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Test connection
psql $DATABASE_URL -c "SELECT 1"

# Check database exists
psql -l | grep bot_order

# Recreate database
dropdb bot_order
createdb bot_order
psql bot_order -f scripts/schema.sql
```

### Webhook Issues
```bash
# Check webhook server running
curl http://localhost:9000/webhooks/pakasir

# Test webhook with dummy data
curl -X POST http://localhost:9000/webhooks/pakasir \
  -H "Content-Type: application/json" \
  -d '{"order_id":"test123","status":"paid"}'

# Check webhook logs
tail -f logs/webhook/$(date +%Y-%m-%d).log
```

---

## 📊 Monitoring

### View Logs
```bash
# Bot logs
tail -f logs/telegram-bot/$(date +%Y-%m-%d).log

# Webhook logs
tail -f logs/webhook/$(date +%Y-%m-%d).log

# Audit logs
tail -f logs/audit/$(date +%Y-%m-%d).log

# Health check logs
tail -f logs/health-check/$(date +%Y-%m-%d).log

# All logs today
tail -f logs/**/$(date +%Y-%m-%d).log
```

### Health Check
```bash
# Run manual health check
python -m src.tools.healthcheck

# Check health check logs
cat logs/health-check/$(date +%Y-%m-%d).log
```

### Database Queries
```bash
# Check total users
psql $DATABASE_URL -c "SELECT COUNT(*) FROM users;"

# Check recent orders
psql $DATABASE_URL -c "SELECT * FROM orders ORDER BY created_at DESC LIMIT 10;"

# Check product stock
psql $DATABASE_URL -c "SELECT name, stock FROM products WHERE stock < 10;"

# Check failed payments
psql $DATABASE_URL -c "SELECT * FROM orders WHERE status = 'failed' ORDER BY created_at DESC;"
```

---

## 💾 Backup & Restore

### Create Backup
```bash
# Manual backup
BACKUP_ENCRYPTION_PASSWORD='your-password' \
python -m src.tools.backup_manager create --offsite

# List backups
python -m src.tools.backup_manager list

# Verify backup
python -m src.tools.backup_manager verify backups/local/backup-*.tar.gz.enc
```

### Restore Backup
```bash
# Restore from backup
BACKUP_ENCRYPTION_PASSWORD='your-password' \
python -m src.tools.backup_manager restore backups/local/backup-20250115-120000.tar.gz.enc

# Restart services after restore
docker compose restart
# or
python -m src.main --mode polling
```

---

## 🔐 Security

### Rotate Bot Token
```bash
# 1. Get new token from @BotFather
# 2. Update .env
sed -i 's/TELEGRAM_BOT_TOKEN=.*/TELEGRAM_BOT_TOKEN=new_token/' .env

# 3. Restart bot
docker compose restart
# or
pkill -f "python -m src.main" && python -m src.main --mode polling &
```

### Check Blocked Users
```bash
psql $DATABASE_URL -c "SELECT user_id, username, blocked_at FROM users WHERE is_blocked = true;"
```

### Audit Recent Admin Actions
```bash
# Check audit logs
grep "admin_action" logs/audit/$(date +%Y-%m-%d).log

# Check who modified products
grep "product" logs/audit/$(date +%Y-%m-%d).log
```

---

## 📝 Common Bot Commands

### For Customers
- `/start` - Start bot dan lihat menu
- Numbers (1️⃣, 2️⃣, etc.) - Quick access products

### For Admin (via Telegram)
- `/admin` - Open admin menu
- `/refund_calculator` - Calculate refunds
- `/set_calculator` - Configure calculator
- `/refund_history` - View refund history

### For Owner (CLI)
```bash
# Health check
python -m src.tools.healthcheck

# Backup management
python -m src.tools.backup_manager create
python -m src.tools.backup_manager list
python -m src.tools.backup_manager restore <file>

# Database operations
psql $DATABASE_URL -c "YOUR SQL QUERY"
```

---

## 🎯 Performance Optimization

### Clear Old Logs (manual)
```bash
# Remove logs older than 30 days
find logs -type f -name "*.log" -mtime +30 -delete

# Compress old logs
find logs -type f -name "*.log" -mtime +7 -exec gzip {} \;
```

### Database Maintenance
```bash
# Vacuum database
psql $DATABASE_URL -c "VACUUM ANALYZE;"

# Reindex
psql $DATABASE_URL -c "REINDEX DATABASE bot_order;"

# Check database size
psql $DATABASE_URL -c "SELECT pg_size_pretty(pg_database_size('bot_order'));"
```

### Monitor Resource Usage
```bash
# Check CPU and memory
top -b -n 1 | grep python

# Check disk space
df -h

# Check log directory size
du -sh logs/
```

---

## 🔄 Update Deployment

### Pull New Version
```bash
# Git pull (if using git)
git pull origin main

# Reinstall dependencies
pip install -r requirements.txt --upgrade

# Run migrations if any
psql $DATABASE_URL -f scripts/migrations/YYYYMMDD_*.sql

# Restart services
docker compose down && docker compose up -d
# or
pkill -f "python -m src.main" && python -m src.main --mode polling &
```

---

## 📞 Emergency Contacts

### Critical Issues
1. Check `logs/telegram-bot/` for error details
2. Review `docs/fixing_plan.md` for known issues
3. Rollback to previous version if needed
4. Document new issue in `docs/fixing_plan.md`

### Rollback Procedure
```bash
# 1. Stop current version
docker compose down
# or
pkill -f "python -m src.main"

# 2. Restore backup
BACKUP_ENCRYPTION_PASSWORD='password' \
python -m src.tools.backup_manager restore backups/local/backup-LATEST.tar.gz.enc

# 3. Checkout previous version (if using git)
git checkout v0.2.1

# 4. Start services
docker compose up -d
# or
python -m src.main --mode polling &
```

---

## 📚 Documentation Reference

- **README.md** - Full setup and deployment guide
- **docs/fixing_plan.md** - Known issues and solutions
- **docs/CHANGELOG.md** - Version history
- **DEPLOYMENT_READY.md** - Deployment checklist and audit results
- **docs/pakasir.md** - Payment gateway integration guide
- **docs/02_prd.md** - Product requirements

---

**Need Help?** Check documentation in `/docs/` folder or review logs in `/logs/` directory.