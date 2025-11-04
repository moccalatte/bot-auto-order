"""Refund Calculator Logic & Tracking.

- Customizable refund formula and fee rules (configurable by admin).
- Calculation logic for refund based on input.
- History tracking for each calculation (order_id, invoice_id, date, input, result).
- Config and history stored in JSON files.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

CONFIG_PATH = "refund_calculator_config.json"
HISTORY_PATH = "refund_calculator_history.json"

DEFAULT_CONFIG = {
    "refund_formula": "(harga * sisa_hari / total_hari) * fee",
    "fee_rules": [
        {"max_days_used": 7, "fee": 0.8},
        {"min_days_used": 8, "fee": 0.7},
        {"garansi_claims": 1, "fee": 0.6},
        {"garansi_claims": 3, "fee": 0.5},
        {"garansi_claims": ">3", "fee": 0.4},
    ],
    "notes": (
        "Penjelasan dan kesepakatan fee refund:\n"
        "0.8 = pemakaian <1 minggu\n"
        "0.7 = pemakaian >1 minggu\n"
        "0.6 = sudah claim garansi 1-2×\n"
        "0.5 = sudah claim garansi 3×\n"
        "0.4 = sudah claim garansi > 3×\n"
        "• 1 bulan dihitung 30 hari.\n"
        "• Fee admin untuk service waktu, tenaga, dll.\n"
        "• Claim refund hanya untuk yang diminta oleh seller."
    ),
}


def load_config(path: str = CONFIG_PATH) -> Dict[str, Any]:
    if not os.path.exists(path):
        save_config(DEFAULT_CONFIG, path)
        return DEFAULT_CONFIG.copy()
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config: Dict[str, Any], path: str = CONFIG_PATH) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def load_history(path: str = HISTORY_PATH) -> list:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_history(history: list, path: str = HISTORY_PATH) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def get_fee(
    sisa_hari: int,
    total_hari: int,
    garansi_claims: int,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Determine fee based on rules."""
    if config is None:
        config = load_config()
    fee = 0.7  # default
    days_used = total_hari - sisa_hari
    for rule in config.get("fee_rules", []):
        if "max_days_used" in rule and days_used <= rule["max_days_used"]:
            fee = rule["fee"]
            break
        if "min_days_used" in rule and days_used >= rule["min_days_used"]:
            fee = rule["fee"]
        if "garansi_claims" in rule:
            if (
                isinstance(rule["garansi_claims"], int)
                and garansi_claims == rule["garansi_claims"]
            ):
                fee = rule["fee"]
            elif isinstance(rule["garansi_claims"], str) and rule[
                "garansi_claims"
            ].startswith(">"):
                min_claims = int(rule["garansi_claims"][1:])
                if garansi_claims > min_claims:
                    fee = rule["fee"]
    return fee


def calculate_refund(
    harga: float,
    sisa_hari: int,
    total_hari: int,
    garansi_claims: int = 0,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Calculate refund amount and details."""
    if config is None:
        config = load_config()
    fee = get_fee(sisa_hari, total_hari, garansi_claims, config)
    try:
        refund = (harga * sisa_hari / total_hari) * fee
    except Exception:
        refund = 0.0
    return {
        "harga": harga,
        "sisa_hari": sisa_hari,
        "total_hari": total_hari,
        "garansi_claims": garansi_claims,
        "fee": fee,
        "refund": round(refund, 2),
        "formula": config.get("refund_formula", ""),
        "notes": config.get("notes", ""),
    }


def add_history(
    order_id: str,
    order_date: str,
    invoice_id: str,
    input_data: Dict[str, Any],
    result: Dict[str, Any],
    user_id: Optional[int] = None,
    history_path: str = HISTORY_PATH,
) -> None:
    """Save calculation history."""
    history = load_history(history_path)
    history.append(
        {
            "order_id": order_id,
            "order_date": order_date,
            "invoice_id": invoice_id,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            "input": input_data,
            "result": result,
        }
    )
    save_history(history, history_path)


def get_history(
    order_id: Optional[str] = None,
    invoice_id: Optional[str] = None,
    user_id: Optional[int] = None,
    history_path: str = HISTORY_PATH,
) -> list:
    """Retrieve calculation history by filter."""
    history = load_history(history_path)
    filtered = []
    for entry in history:
        if order_id and entry.get("order_id") != order_id:
            continue
        if invoice_id and entry.get("invoice_id") != invoice_id:
            continue
        if user_id and entry.get("user_id") != user_id:
            continue
        filtered.append(entry)
    return filtered


def update_config(new_config: Dict[str, Any], path: str = CONFIG_PATH) -> None:
    """Update config with new values."""
    config = load_config(path)
    config.update(new_config)
    save_config(config, path)
