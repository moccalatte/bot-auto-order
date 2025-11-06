#!/usr/bin/env bash
# Cleanup and Fix Script for bot-auto-order
# Removes all Python bytecode cache and recompiles everything fresh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "🔧 Bot Auto-Order Cleanup & Fix Script"
echo "📁 Project root: ${PROJECT_ROOT}"
echo ""

cd "${PROJECT_ROOT}"

# Step 1: Remove all Python cache
echo "🧹 Step 1: Cleaning Python bytecode cache..."
find . -type d -name "__pycache__" -print0 | xargs -0 rm -rf 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true
find . -type d -name "*.egg-info" -print0 | xargs -0 rm -rf 2>/dev/null || true
echo "✅ Cache cleaned"
echo ""

# Step 2: Verify Python version
echo "🐍 Step 2: Verifying Python environment..."
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
echo "   Python version: ${PYTHON_VERSION}"

# Check if in virtual environment
if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    echo "   Virtual environment: ${VIRTUAL_ENV}"
    echo "✅ Running in virtual environment"
else
    echo "⚠️  WARNING: Not running in a virtual environment!"
    echo "   It's recommended to activate venv first:"
    echo "   source venv/bin/activate"
    echo ""
fi
echo ""

# Step 3: Compile all Python files
echo "🔨 Step 3: Compiling all Python files..."
if python -m compileall -q src/ 2>&1; then
    echo "✅ All Python files compiled successfully"
else
    echo "❌ Compilation failed! Check for syntax errors."
    exit 1
fi
echo ""

# Step 4: Run import checker
echo "🔍 Step 4: Running comprehensive import checker..."
if [[ -f "scripts/check_imports.py" ]]; then
    python scripts/check_imports.py
    IMPORT_CHECK_STATUS=$?
else
    echo "⚠️  Import checker not found, skipping..."
    IMPORT_CHECK_STATUS=0
fi
echo ""

# Step 5: Verify critical imports
echo "✅ Step 5: Verifying critical imports..."
CRITICAL_IMPORTS=(
    "src.services.users:get_user_by_telegram_id"
    "src.services.catalog:add_product"
    "src.services.payment:PaymentService"
    "src.services.postgres:get_pool"
)

FAILED_IMPORTS=0
for import_spec in "${CRITICAL_IMPORTS[@]}"; do
    module="${import_spec%%:*}"
    name="${import_spec##*:}"

    if python -c "from ${module} import ${name}; print('  ✅ ${module}.${name}')" 2>/dev/null; then
        true
    else
        echo "  ❌ Failed to import ${name} from ${module}"
        FAILED_IMPORTS=$((FAILED_IMPORTS + 1))
    fi
done

if [[ ${FAILED_IMPORTS} -gt 0 ]]; then
    echo ""
    echo "❌ ${FAILED_IMPORTS} critical import(s) failed!"
    echo "   This might be due to missing dependencies."
    echo "   Try: pip install -r requirements.txt"
    exit 1
fi
echo "✅ All critical imports verified"
echo ""

# Step 6: Final summary
echo "════════════════════════════════════════════════════════════════"
echo "📊 CLEANUP & FIX SUMMARY"
echo "════════════════════════════════════════════════════════════════"
echo "✅ Python cache cleaned"
echo "✅ All files compiled successfully"
if [[ ${IMPORT_CHECK_STATUS} -eq 0 ]]; then
    echo "✅ Import checker passed"
else
    echo "⚠️  Import checker found issues (see above)"
fi
echo "✅ Critical imports verified"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "🎉 Cleanup and fix completed successfully!"
echo ""
echo "📝 Next steps:"
echo "   1. If not in venv: source venv/bin/activate"
echo "   2. Start bot: TELEGRAM_MODE=polling ./scripts/run_stack.sh"
echo "   3. Monitor logs: tail -f logs/bot_*.log"
echo ""

exit 0
