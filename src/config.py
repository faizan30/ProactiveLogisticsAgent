"""
Configuration for the Celonis Garage demo.
"""
import os
from dotenv import load_dotenv

load_dotenv()


# ==================== DATABASE ====================

def get_db_connection_string() -> str:
    """Build PostgreSQL connection string from environment variables."""
    user = os.environ.get("POSTGRES_USER")
    password = os.environ.get("POSTGRES_PASSWORD")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB")
    
    missing = []
    if not user:
        missing.append("POSTGRES_USER")
    if not password:
        missing.append("POSTGRES_PASSWORD")
    if not db:
        missing.append("POSTGRES_DB")
    
    if missing:
        raise EnvironmentError(
            f"Missing required database environment variables: {', '.join(missing)}. "
            "Please set them in .env file or environment."
        )
    
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def get_openai_api_key() -> str:
    """Get OpenAI API key from environment."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise EnvironmentError("Missing OPENAI_API_KEY environment variable.")
    return key


# ==================== KPI THRESHOLDS ====================
# Used by RiskEngine to detect deviations

THRESHOLDS = {
    # Hub threshold - max hours at destination hub before breach
    "hub_hours": 24,
    
    # Transit threshold - buffer hours over route average
    "transit_buffer_hours": 24,
    
    # Deadline pressure - hours remaining that triggers concern
    "deadline_pressure_hours": 48,
    
    # Route risk threshold - failure rate above this = high risk
    "route_failure_rate": 0.5,
    
    # Default transit hours for unknown routes (7 days)
    "default_transit_hours": 168,
}


# ==================== SEVERITY WEIGHTS ====================
# Configurable severity levels for each KPI breach

SEVERITY_CONFIG = {
    "hub_hours": "HIGH",           # Package stuck at hub
    "transit_hours": "MEDIUM",     # Slow transit
    "hours_remaining": "CRITICAL", # Overdue
    "route_failure_rate": "MEDIUM",# High-risk route
    "predicted_delay": "HIGH",     # Composite delay prediction
    "ticket_raised": "CRITICAL",   # Customer escalation
}


# ==================== KPI BASELINE VALUES ====================
# Used for normalization in KPI calculations

KPI_CONFIG = {
    "tolerance_default_rating": 3,      # Default customer rating if missing
    "tolerance_max_calls": 5,           # 5+ calls = max frustration
    "default_transit_hours": 168,       # 7 days default for unknown routes
}


# ==================== AGENT CONFIG ====================

AGENT_CONFIG = {
    "model": "gpt-4o",
    "max_turns": 5,               # Max conversation turns per scenario
    "max_refund_percent": 20,     # Max refund without escalation (%)
}
