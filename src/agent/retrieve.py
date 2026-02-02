"""
Simple file retrieval for agent tools.

Reads data files (policy.md, customer_stats.json) and returns content.
No complex logic - downstream LLM processes the raw content.
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"
POLICY_FILE = DATA_DIR / "policy.md"
CUSTOMER_STATS_FILE = DATA_DIR / "customer_stats.json"


def get_policy() -> str:
    """Read and return the full policy document."""
    if POLICY_FILE.exists():
        return POLICY_FILE.read_text()
    return "Policy file not found."


def get_customer_stats() -> dict:
    """Read and return customer stats by rating."""
    if CUSTOMER_STATS_FILE.exists():
        return json.loads(CUSTOMER_STATS_FILE.read_text())
    return {}
