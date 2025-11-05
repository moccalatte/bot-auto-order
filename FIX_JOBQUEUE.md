# 🔧 Fix JobQueue Warning - Installation Guide

## Problem
```
PTBUserWarning: No `JobQueue` set up. To use `JobQueue`, you must install PTB via `pip install "python-telegram-bot[job-queue]"`
```

## Root Cause
The virtual environment doesn't have the updated `requirements.txt` installed with `[job-queue]` extra.

## Solution

### Step 1: Activate Virtual Environment
```bash
cd ~/dev/code/bot-auto-order
source venv/bin/activate
```

### Step 2: Upgrade pip (recommended)
```bash
pip install --upgrade pip
```

### Step 3: Install/Upgrade Requirements
```bash
# Uninstall old version first
pip uninstall python-telegram-bot -y

# Install new version with job-queue support
pip install -r requirements.txt

# Or install directly:
pip install "python-telegram-bot[webhooks,job-queue]==21.3"
```

### Step 4: Verify Installation
```bash
python -c "from telegram.ext import JobQueue; print('✅ JobQueue available!')"
```

Expected output:
```
✅ JobQueue available!
```

### Step 5: Restart Bot
```bash
# Stop any running instance
pkill -f "python -m src.main"

# Start bot
TELEGRAM_MODE=polling ./scripts/run_stack.sh
```

## Verification Checklist

After restart, check that:
- [ ] No JobQueue warnings in logs
- [ ] Bot starts successfully
- [ ] `/start` command works
- [ ] Admin keyboard appears for admin users
- [ ] Customer keyboard appears for regular users

## If Still Not Working

### Option 1: Recreate Virtual Environment
```bash
cd ~/dev/code/bot-auto-order

# Deactivate current venv
deactivate

# Remove old venv
rm -rf venv

# Create new venv
python3.12 -m venv venv
source venv/bin/activate

# Install all requirements fresh
pip install --upgrade pip
pip install -r requirements.txt
```

### Option 2: Check Python Version
```bash
python --version
# Should be Python 3.12+
```

If using wrong Python version:
```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Option 3: Manual Installation
```bash
pip install python-telegram-bot==21.3
pip install python-telegram-bot[webhooks]
pip install python-telegram-bot[job-queue]
pip install APScheduler~=3.10.4
```

## Why This Happened

The `requirements.txt` was recently updated from:
```
python-telegram-bot[webhooks]==21.3
```

To:
```
python-telegram-bot[webhooks,job-queue]==21.3
```

But the virtual environment wasn't reinstalled, so it still has the old version without job-queue support.

## After Fix

You should see clean startup logs like:
```
[2025-11-05 21:22:45] [INFO] 📈 TelemetryTracker started.
[2025-11-05 21:22:45] [INFO] 🔌 Connected to Postgres.
[2025-11-05 21:22:45] [INFO] ▶️ Starting bot in polling mode.
[2025-11-05 21:22:46] [INFO] ✅ Bot initialised.
```

**WITHOUT** any JobQueue warnings!

---

**Last Updated:** 2025-01-15  
**Status:** ✅ Tested and Verified