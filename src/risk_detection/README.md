# Risk Detection Engine - Design Document

This module implements threshold-based risk detection for logistics shipments using Key Performance Indicators (KPIs) to proactively identify at-risk orders before they become customer complaints.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         RiskEngine                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │   KPIs       │  │ Route Stats  │  │   Detection Rules    │   │
│  │  (5 classes) │  │   (JSON)     │  │   (Priority-based)   │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   RiskSignal     │
                    │  - signal_type   │
                    │  - severity      │
                    │  - reason        │
                    │  - kpis          │
                    └──────────────────┘
```

---

## KPI Definitions

### 1. HubHoursKPI

**Purpose:** Detect packages sitting idle at destination hub without final delivery.

| Property | Value |
|----------|-------|
| **Metric** | Hours since arrival at destination hub |
| **Threshold** | 24 hours |
| **Breach** | `hub_hours > 24` |
| **Severity** | HIGH |

**Rationale:** A package at the destination hub should be out for delivery within 24 hours. Beyond this indicates operational issues (missed delivery attempts, address problems, capacity constraints).

**Calculation:**
```python
if destination_arrival_date and not actual_delivery_date:
    hub_hours = (now - destination_arrival_date).total_seconds() / 3600
else:
    hub_hours = 0  # Not at hub or already delivered
```

**Edge Cases:**
| Condition | Behavior |
|-----------|----------|
| No arrival date | Returns 0 (still in transit) |
| Already delivered | Returns 0 (no issue) |
| Arrival date in future | Returns negative (data error, treat as 0) |
| Exactly at threshold (24h) | NOT breached (uses `>`) |

**Boundary Conditions:**
- 24.0h → Not breached
- 24.1h → Breached
- Uses hours to avoid day-boundary precision issues

---

### 2. TransitHoursKPI

**Purpose:** Detect packages taking longer than expected to reach destination hub.

| Property | Value |
|----------|-------|
| **Metric** | Hours in transit (shipped but not arrived) |
| **Threshold** | Dynamic: `route_avg_hours + 24h` (route+mode specific) |
| **Breach** | `transit_hours > threshold` |
| **Severity** | MEDIUM |

**Route+Mode Specific Thresholds:**

The threshold is dynamically calculated based on historical data for each route+mode combination:

```
Route Key Format: "{origin_region}_{destination_region}_{mode_of_shipment}"

Example:
  Order: origin="South", dest="Midwest", mode="Flight"
  Route Key: "South_Midwest_Flight"
  Lookup: route_stats["South_Midwest_Flight"]["avg_transit_days"] = 2.0
  Threshold: (2.0 * 24) + 24 = 72 hours
```

**Rationale:** Different routes have different expected transit times (Flight: 4-6 days, Road: 5-9 days, Ship: 7-10 days). A fixed threshold doesn't account for this variance. Using route-specific historical average + 24h buffer flags truly anomalous delays.

**Calculation:**
```python
route_key = f"{origin_region}_{destination_region}_{mode_of_shipment}"
route_avg = route_stats.get(route_key, {}).get("avg_transit_days", 7) * 24
threshold = route_avg + buffer  # Dynamic per route+mode
```

**Edge Cases:**
| Condition | Behavior |
|-----------|----------|
| Not shipped yet | Returns 0 |
| Already arrived at hub | Returns 0 |
| Unknown route | Uses 168h (7 days) as default avg |
| Zero avg_transit_days | Uses minimum 24h (1 day) |
| Ship date in future | Clamped to 0 |

**Boundary Conditions:**
- Route avg 5 days (120h) → threshold = 144h
- Transit 144h → Not breached
- Transit 144.1h → Breached

---

### 3. HoursRemainingKPI

**Purpose:** Detect overdue shipments (past promised delivery date).

| Property | Value |
|----------|-------|
| **Metric** | Hours until promised delivery (negative = overdue) |
| **Threshold** | 0 |
| **Breach** | `hours_remaining < 0` |
| **Severity** | CRITICAL |

**Rationale:** Simplified from previous buffer-based approach. A breach occurs only when the package is actually overdue. This is a clear, actionable signal - the customer's expectation has already been violated.

**Calculation:**
```python
if promised_date:
    hours_remaining = (promised_date - now).total_seconds() / 3600
else:
    hours_remaining = 9999  # No deadline, no breach
```

**Edge Cases:**
| Condition | Behavior |
|-----------|----------|
| No promised date | Returns 9999 (no deadline) |
| Promised date exactly now | Returns 0 (not yet overdue) |
| Order already delivered | Still calculates (for historical analysis) |

**Boundary Conditions:**
- 0.1h remaining → Not breached
- 0h remaining → Not breached (at threshold)
- -0.1h → Breached (overdue)

**Design Decision:** We removed the "buffer" concept (warning when close to deadline) because:
1. It created false alarms for on-time deliveries
2. PredictedDelayKPI now handles proactive warning
3. Simpler logic = more maintainable

---

### 4. RouteRiskKPI

**Purpose:** Flag shipments on historically problematic route+mode combinations.

| Property | Value |
|----------|-------|
| **Metric** | Historical failure rate (0.0 - 1.0) per route+mode |
| **Threshold** | 0.5 (50%) |
| **Breach** | `failure_rate > 0.5` |
| **Severity** | MEDIUM |

**Route+Mode Specific Lookup:**

```
Route Key Format: "{origin_region}_{destination_region}_{mode_of_shipment}"

Example:
  Order: origin="West", dest="East", mode="Road"
  Route Key: "West_East_Road"
  Lookup: route_stats["West_East_Road"]["failure_rate"] = 0.6
  Result: 60% failure rate → HIGH RISK
```

**Rationale:** Some route+mode combinations consistently have higher failure rates due to infrastructure, weather patterns, or carrier issues. The same route via Flight may be reliable while Road is problematic.

**Calculation:**
```python
route_key = f"{origin}_{destination}_{mode}"
failure_rate = route_stats.get(route_key, {}).get("failure_rate", 0.5)
```

**Edge Cases:**
| Condition | Behavior |
|-----------|----------|
| Unknown route | Returns 0.5 (moderate risk assumed) |
| Missing region/mode | Key becomes `None_None_None` → 0.5 |

**Design Decision:** Unknown routes default to 0.5 (not 0.0) because:
1. No data doesn't mean no risk
2. New routes should be monitored more carefully
3. Avoids false "safe" signals

**Route Stats Analysis:**
- Failure rates in dataset: 0.29 - 0.51
- Only ~5% of routes exceed 0.5 threshold
- These represent genuinely problematic route/mode combinations

---

### 5. PredictedDelayKPI

**Purpose:** Composite KPI that proactively predicts if delivery will be late.

| Property | Value |
|----------|-------|
| **Metric** | Boolean prediction |
| **Breach** | Composite logic (see below) |
| **Severity** | HIGH |
| **Priority** | Primary signal for PREDICTED_DELAY |

**Rationale:** This is the key proactive KPI. Instead of waiting for actual delays, it combines multiple signals to predict problems before they occur, enabling intervention.

**Calculation:**
```python
# Predict delay if ANY condition is true:

# 1. Already overdue
is_overdue = hours_remaining < 0

# 2. Transit significantly slow AND deadline pressure
is_transit_slow = transit_hours > (route_avg_hours + 24)
has_deadline_pressure = hours_remaining < 48  # Less than 2 days

# 3. High-risk route AND deadline pressure (proactive warning)
is_high_risk_route = route_failure_rate > 0.5

predicted_delay = (
    is_overdue or 
    (is_transit_slow and has_deadline_pressure) or
    (is_high_risk_route and has_deadline_pressure)  # Route risk alone triggers warning
)
```

**Edge Cases:**
| Condition | Behavior |
|-----------|----------|
| All inputs missing | Returns False (no prediction possible) |
| No promised date | No deadline pressure, less likely to predict delay |
| On track with risky route | Not breached unless also slow |

**Design Decision:** We include route risk in the prediction because:
1. High-risk routes have 50%+ historical failure
2. Combined with slow transit, this is a strong signal
3. Enables proactive intervention on known problem routes

---

## RiskEngine Detection Rules

### Signal Priority (Highest to Lowest)

```
1. TICKET_RAISED   → Customer already complained (reactive)
2. STUCK_AT_HUB    → Package idle at hub > 24h (actionable)
3. PREDICTED_DELAY → Proactive delay prediction (preventive)
4. ON_TRACK        → No issues detected (default)
```

### Detection Logic

```python
def detect(self, order, now):
    kpi_result = self.calculate_kpis(order, now)
    kpis = kpi_result.kpis
    breaches = kpi_result.breaches
    
    # Priority 1: Customer ticket (reactive - highest priority)
    # Rationale: Customer has already escalated, requires immediate response
    if kpis["ticket_raised"] == 1:
        return RiskSignal(TICKET_RAISED, severity=CRITICAL)
    
    # Priority 2: Stuck at hub (actionable)
    # Rationale: Clear operational issue that can be resolved
    hub_breach = self._get_breach(breaches, "hub_hours")
    if hub_breach:
        return RiskSignal(STUCK_AT_HUB, severity=HIGH)
    
    # Priority 3: Predicted delay (proactive)
    # Rationale: Opportunity to intervene before customer impact
    predicted_breach = self._get_breach(breaches, "predicted_delay")
    if predicted_breach:
        return RiskSignal(PREDICTED_DELAY, severity=HIGH)
    
    # Default: On track
    return RiskSignal(ON_TRACK, severity=LOW)
```

### Why This Priority Order?

1. **TICKET_RAISED first:** Customer pain is real and immediate. All other signals become secondary when a ticket exists.

2. **STUCK_AT_HUB second:** This is the most actionable signal. The package is physically located, and operations can intervene (contact hub, arrange redelivery, etc.).

3. **PREDICTED_DELAY third:** This is proactive but less certain. It's a prediction, not a confirmed problem. Intervention here is about managing expectations.

4. **ON_TRACK default:** Absence of negative signals. No action needed.

---

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Customer impacted, immediate action | Empathy + compensation |
| HIGH | Likely to impact customer soon | Proactive outreach |
| MEDIUM | Potential issue, monitor | Internal alert |
| LOW | No issues | No action |

---

## KPIs Considered But Not Implemented

### 1. CustomerSentimentKPI

**Idea:** Use customer rating and care call history to predict escalation risk.

**Why not implemented:**
- `customer_rating` is historical (from past orders), not current sentiment
- `customer_care_calls` for current order is already captured in `ticket_raised`
- Would require NLP analysis of call transcripts for real value

**Future consideration:** If call transcript data becomes available, sentiment analysis could add value.

### 2. ProductValueKPI

**Idea:** High-value products (>$250) should get priority handling.

**Why not implemented:**
- Risk detection should be based on delivery performance, not product value
- Value-based prioritization belongs in agent response, not detection
- Could create bias toward wealthy customers

**Note:** Product cost IS available in order data and can be used by the agent when crafting responses.

### 3. SeasonalityKPI

**Idea:** Adjust thresholds based on peak seasons (holidays, sales events).

**Why not implemented:**
- Requires historical seasonal data we don't have
- Would add complexity without clear immediate value
- Can be added later as a threshold modifier

### 4. WeatherImpactKPI

**Idea:** Factor in weather disruptions along the route.

**Why not implemented:**
- Requires real-time weather API integration
- Route geometry data needed for weather mapping
- Out of scope for current demo

### 5. CarrierPerformanceKPI

**Idea:** Track performance by carrier/mode combination.

**Why not implemented:**
- Dataset doesn't include carrier identification
- Route stats already capture mode-based performance
- Would duplicate RouteRiskKPI functionality

---

## Timezone Handling

Currently assumes single timezone (server local time). A placeholder function `get_current_time()` is provided in `kpis.py` for future multi-timezone support.

```python
def get_current_time() -> datetime:
    """
    TODO: For multi-timezone support, return timezone-aware datetime.
    Currently assumes single timezone (server local time).
    """
    return datetime.now()
```

---

## Configuration

Thresholds are defined in `src/config.py`:

```python
THRESHOLDS = {
    "hub_hours": 24,                    # Max hours at hub
    "transit_buffer_hours": 24,         # Buffer over route average
    "deadline_pressure_hours": 48,      # Hours remaining = pressure
    "route_failure_rate": 0.5,          # High-risk route threshold
    "default_transit_hours": 168,       # 7 days for unknown routes
}
```

---

## Testing Strategy

### Unit Tests (per KPI)
- Normal calculation
- Edge cases (missing dates, future dates)
- Boundary conditions (exactly at threshold)
- Breach detection accuracy

### Integration Tests (RiskEngine)
- Priority ordering verification
- Composite KPI interaction
- Demo scenario coverage

### Demo Scenarios

| ID | Scenario | Expected Signal |
|----|----------|-----------------|
| 1001 | Happy path | ON_TRACK |
| 1002 | Predicted delay | PREDICTED_DELAY |
| 1003 | Stuck at hub | STUCK_AT_HUB |
| 1004 | Ticket raised | TICKET_RAISED |

---

## Future Enhancements

1. **ML-based prediction:** Replace rule-based PredictedDelayKPI with trained model
2. **Real-time updates:** Stream processing for continuous monitoring
3. **Threshold tuning:** A/B test different thresholds for optimal precision/recall
4. **Multi-signal fusion:** Bayesian combination of KPI signals
5. **Feedback loop:** Learn from agent intervention outcomes
