# Risk Detection Engine

Threshold-based KPI monitoring for proactive logistics issue detection.

## 5 KPIs Implemented

| KPI | Measures | Threshold | Purpose |
|-----|----------|-----------|---------|
| **HubHoursKPI** | Hours at destination hub | 24h | Detect stuck packages |
| **TransitHoursKPI** | Hours in transit | Route avg + 24h | Route-specific delays |
| **HoursRemainingKPI** | Time until promised date | 0h (overdue) | Deadline breach |
| **RouteRiskKPI** | Route failure rate | 50% | High-risk routes |
| **PredictedDelayKPI** | Composite signal | Multiple conditions | Proactive prediction |

## Signal Priority

Detection returns highest-priority signal:

1. **TICKET_RAISED** (Critical) — Customer already escalated
2. **STUCK_AT_HUB** (High) — Package idle at hub 24h+
3. **PREDICTED_DELAY** (High) — Composite prediction of delay
4. **ON_TRACK** (Low) — No issues detected

## Dynamic Thresholds

**TransitHoursKPI** uses route-specific thresholds from `route_stats.json`:

```python
# Example: South_Midwest_Flight
route_avg = 2.1 days  # From historical data
threshold = (2.1 * 24) + 24 = 74.4 hours

# vs West_East_Road
route_avg = 7.8 days
threshold = (7.8 * 24) + 24 = 211.2 hours
```

**Why dynamic?** Fixed threshold would:
- ❌ False alarms on long routes (8-day Road shipment)
- ❌ Miss issues on short routes (Flight delayed to 70h)

## Usage

```python
from src.risk_detection import RiskEngine

engine = RiskEngine()
signal = engine.detect(order)
# Returns: RiskSignal(type="PREDICTED_DELAY", severity="HIGH", ...)
```

```bash
curl http://localhost:9001/detect-deviation/1002
```

## PredictedDelayKPI Logic

Composite KPI combining multiple signals:

```python
predicted_delay = (
    is_overdue                           # Already past promised date
    OR (transit_slow AND deadline_soon)  # Slow transit + time pressure
    OR (high_risk_route AND deadline_soon) # Known bad route + pressure
)
```

This enables **proactive intervention** before customer notices.

## Configuration

Thresholds in `src/config.py`:

```python
THRESHOLDS = {
    "hub_hours": 24,
    "transit_buffer_hours": 24,
    "deadline_pressure_hours": 48,
    "route_failure_rate": 0.5,
    "default_transit_hours": 168,  # 7 days for unknown routes
}
```

## Full Details

See [`documentation/Architecture.md`](../../documentation/Architecture.md) for:
- Complete KPI design rationale
- Edge cases and boundary conditions
- Failure modes and validation
- Production considerations
