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
    # Time-based thresholds
    "hub_hours": 48,            
    "transit_days": 3,   
    "days_remaining_buffer": 2,
    
    # Route risk threshold  
    "route_failure_rate": 0.5,    # 40% failure rate = high risk route
}


# ==================== KPI BASELINE VALUES ====================
# Used for normalization in KPI calculations

KPI_CONFIG = {
    "tolerance_default_rating": 3,      # Default customer rating if missing
    "tolerance_max_calls": 5,           # 5+ calls = max frustration
    "velocity_default_transit_days": 3.0,  # Default transit days for velocity model
}


# ==================== AGENT CONFIG ====================

AGENT_CONFIG = {
    "model": "gpt-4o",
    "max_turns": 5,               # Max conversation turns per scenario
    "max_refund_percent": 20,     # Max refund without escalation (%)
}
