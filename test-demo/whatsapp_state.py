"""
WhatsApp Conversation State Store
=================================
Maintains conversation stages, requirements, and lead context for incoming WhatsApp chats.
Uses persistent JSON file storage with optional Redis fallback.
"""

import json
import os
import time
from typing import Dict, Any

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "whatsapp_states.json")
_mem_cache: Dict[str, Dict[str, Any]] = {}
_redis_client = None

# Optional Redis init if available in environment
try:
    if os.getenv("REDIS_HOST"):
        import redis
        _redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=0,
            decode_responses=True
        )
except Exception:
    _redis_client = None


def _ensure_dir():
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)


def _load_disk_states() -> Dict[str, Any]:
    _ensure_dir()
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_disk_states(data: Dict[str, Any]):
    _ensure_dir()
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def get_state(phone: str) -> Dict[str, Any]:
    """Retrieves conversation state for a specific sender phone number."""
    clean_phone = phone.replace("+", "").strip()

    if _redis_client:
        try:
            raw = _redis_client.get(f"whatsapp_lead:{clean_phone}")
            if raw:
                return json.loads(raw)
        except Exception:
            pass

    if clean_phone in _mem_cache:
        return _mem_cache[clean_phone].copy()

    all_states = _load_disk_states()
    state = all_states.get(clean_phone, {
        "stage": "new",
        "requirement": "",
        "source": "WhatsApp inbound enquiry",
        "created_at": time.time(),
        "history": []
    })
    _mem_cache[clean_phone] = state
    return state.copy()


def save_state(phone: str, state: Dict[str, Any]):
    """Saves conversation state for a specific sender phone number."""
    clean_phone = phone.replace("+", "").strip()
    state["updated_at"] = time.time()
    _mem_cache[clean_phone] = state

    if _redis_client:
        try:
            _redis_client.setex(
                f"whatsapp_lead:{clean_phone}",
                60 * 60 * 24 * 30,  # 30-day TTL
                json.dumps(state, ensure_ascii=False)
            )
        except Exception:
            pass

    all_states = _load_disk_states()
    all_states[clean_phone] = state
    _save_disk_states(all_states)
