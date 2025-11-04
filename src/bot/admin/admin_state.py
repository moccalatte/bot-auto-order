"""Helper utilities to keep track of admin interaction state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple


ADMIN_STATE_KEY = "admin_state"


@dataclass(slots=True)
class AdminState:
    """Represent current admin interaction state."""

    action: str
    payload: Dict[str, Any] = field(default_factory=dict)


def set_admin_state(user_data: Dict[str, Any], action: str, **payload: Any) -> None:
    """Store current state for admin interaction."""
    user_data[ADMIN_STATE_KEY] = {"action": action, "payload": payload}


def get_admin_state(user_data: Dict[str, Any]) -> Optional[AdminState]:
    """Return current admin interaction state, if any."""
    raw = user_data.get(ADMIN_STATE_KEY)
    if not isinstance(raw, dict):
        return None
    action = raw.get("action")
    if not isinstance(action, str):
        return None
    payload = raw.get("payload") if isinstance(raw.get("payload"), dict) else {}
    return AdminState(action=action, payload=payload)


def clear_admin_state(user_data: Dict[str, Any]) -> None:
    """Clear stored admin interaction state."""
    user_data.pop(ADMIN_STATE_KEY, None)


def get_state_action(user_data: Dict[str, Any]) -> Optional[str]:
    """Return only action string from admin state."""
    state = get_admin_state(user_data)
    return state.action if state else None


def update_state_payload(user_data: Dict[str, Any], **updates: Any) -> None:
    """Update payload for existing admin state."""
    state = get_admin_state(user_data)
    if state is None:
        return
    state.payload.update(updates)
    user_data[ADMIN_STATE_KEY] = {"action": state.action, "payload": state.payload}


def pop_admin_state(user_data: Dict[str, Any]) -> Optional[AdminState]:
    """Return state and clear it."""
    state = get_admin_state(user_data)
    clear_admin_state(user_data)
    return state
