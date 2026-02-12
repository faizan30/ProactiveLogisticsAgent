# Data Directory

Datasets for the Proactive Logistics Agent - demonstrating LLM-driven data enrichment for logistics KPI calculation.

## Files

| File | Purpose | Source |
|------|---------|--------|
| `Original_data.csv` | Kaggle customer analytics dataset | [Kaggle Dataset](https://www.kaggle.com/) |
| `Enriched_Data_Final.csv` | Enriched with 16 synthetic logistics columns | Gemini Pro LLM |
| `route_stats.json` | Route performance statistics (75 routes) | Generated from enriched CSV |
| `customer_stats.json` | Customer behavior by rating (1-5) | Generated from enriched CSV |
| `policy.md` | Company resolution policies | Handcrafted for demo |

---

## Schema Evolution: Original → Enriched

### Original Kaggle Dataset (12 columns)

**Source:** E-commerce customer analytics dataset  
**Rows:** 10,999  
**Problem:** Missing temporal and logistics fields needed for proactive risk detection

| Column | Type | Description | Demo Limitation |
|--------|------|-------------|-----------------|
| `ID` | int | Order identifier | ✅ Usable as-is |
| `Warehouse_block` | char | Warehouse section (A-F) | ✅ Usable |
| `Mode_of_Shipment` | str | Ship, Flight, Road | ✅ Usable |
| `Customer_care_calls` | int | Support calls count | ✅ Usable |
| `Customer_rating` | int | 1-5 rating | ✅ Usable |
| `Cost_of_the_Product` | int | Order value ($) | ✅ Usable |
| `Prior_purchases` | int | Customer history | ✅ Usable |
| `Product_importance` | str | low/medium/high | ✅ Usable |
| `Gender` | char | M/F | ✅ Usable |
| `Discount_offered` | int | Discount % | ✅ Usable |
| `Weight_in_gms` | int | Package weight | ✅ Usable |
| `Reached.on.Time_Y.N` | bool | 0=late, 1=on-time | ⚠️ Outcome only, no timeline |

**Missing for KPIs:**
- ❌ No timestamps → Can't calculate hub hours, transit time
- ❌ No regions → Can't do route-specific analysis
- ❌ No delivery status → Can't detect stuck packages
- ❌ No ticket flag → Can't identify escalations

---

### Enriched Dataset (28 columns = 12 original + 16 added)

**Enrichment Method:** Gemini Pro LLM with logistics domain prompts  
**Validation:** Cross-checked distributions, realistic date sequences, no nulls in critical fields

### Added Columns & Rationale

#### 1. Temporal Fields (5 columns) - **Critical for KPIs**

| Column | Type | Why Added | Used By |
|--------|------|-----------|---------|
| `Order_Date` | timestamp | Establish timeline baseline | Gap calculations |
| `Promised_Date` | timestamp | SLA deadline for customer | `HoursRemainingKPI` |
| `Ship_Date` | timestamp | When package left warehouse | `TransitHoursKPI` |
| `Destination_Arrival_Date` | timestamp | Hub arrival time | `HubHoursKPI` |
| `Actual_Delivery_Date` | timestamp | Final delivery (if completed) | Status verification |

**Rationale:** Without timestamps, impossible to calculate time-based KPIs (hub delay, transit time, deadline pressure). These are the foundation of proactive detection.

**LLM Generation Logic:**
- `Order_Date`: Random dates in 2024 (6 months back)
- `Promised_Date`: Order + 3-5 days (normal SLA)
- `Ship_Date`: Order + 0-5 days (warehouse processing)
- `Destination_Arrival_Date`: Ship + transit time (varies by mode)
- `Actual_Delivery_Date`: Null if delayed/lost, or Arrival + 0-12 days

#### 2. Geographic Fields (2 columns) - **Route-Specific Analysis**

| Column | Type | Why Added | Used By |
|--------|------|-----------|---------|
| `Origin_Region` | str | Warehouse region (North/South/East/West/Midwest) | Route key generation |
| `Destination_Region` | str | Customer region | `RouteRiskKPI`, route stats |

**Rationale:** Different routes have different failure rates and transit times. "West_East_Flight" may be reliable while "South_North_Road" is problematic. This enables dynamic KPI thresholds.

**LLM Generation:** Realistic US region pairs with logical warehouse-to-customer patterns.

#### 3. Status & Cause Fields (2 columns) - **Signal Detection**

| Column | Type | Why Added | Used By |
|--------|------|-----------|---------|
| `Final_Status` | str | Delivered, In_Transit, At_Hub, Lost, Rescheduled, Refunded | Risk signal classification |
| `Delay_Cause` | str | Transit, Warehouse, LastMile, Address, null | Root cause analysis |

**Rationale:** Need to differentiate between "stuck at hub" vs "slow in transit" vs "already delivered". `Final_Status` maps directly to risk signals.

**Values:**
- `Delivered`: Package completed successfully
- `In_Transit`: Currently moving between origin and hub
- `At_Hub`: Arrived at destination hub, awaiting final delivery
- `Lost`: Package disappeared in transit
- `Rescheduled`: Customer requested new date
- `Refunded`: Customer refunded due to delay

#### 4. Payment Fields (2 columns) - **Resolution Context**

| Column | Type | Why Added | Used By |
|--------|------|-----------|---------|
| `Payment_Status` | str | Paid, Refunded, Pending | Refund eligibility |
| `Payment_Mode` | str | Paid, COD | Agent decision context |

**Rationale:** Agent needs to know if refund already processed, and whether order is prepaid (easier refund) or COD (reschedule preferred).

#### 5. Customer Segmentation (1 column) - **Personalization**

| Column | Type | Why Added | Used By |
|--------|------|-----------|---------|
| `Customer_type` | str | Consumer, Corporate | Agent tone/approach |

**Rationale:** Corporate customers may need different handling (bulk order policies, account managers). Influences agent communication style.

#### 6. Support Escalation (1 column) - **Priority Signal**

| Column | Type | Why Added | Used By |
|--------|------|-----------|---------|
| `Ticket_Raised` | bool | 1 if customer opened ticket | `TICKET_RAISED` signal (highest priority) |

**Rationale:** Most critical signal - customer already complained. This gets top priority in risk detection hierarchy.

**Mapping:** Derived from `Customer_care_calls > 3` in original data.

#### 7. Pre-calculated Gaps (3 columns) - **Performance Shortcuts**

| Column | Type | Why Added | Used By |
|--------|------|-----------|---------|
| `Gap_Shipping_Days` | int | Days from order to ship | Warehouse efficiency |
| `Gap_Transit_Days` | int | Days from ship to hub arrival | Transit performance |
| `Gap_SLA_Days` | float | Days overdue (negative=on-time) | SLA compliance |

**Rationale:** Pre-calculated for data exploration. **Not used by KPIs** (which calculate real-time from timestamps).

---

## Route Statistics (`route_stats.json`)

**Generated from enriched CSV** using `src/data_preprocessing/route_stats_generator.py`

### Purpose
Provide **dynamic, route-specific thresholds** for `TransitHoursKPI` and `RouteRiskKPI`.

### Schema
```json
{
  "{Origin}_{Destination}_{Mode}": {
    "failure_rate": float,      // % of orders late/lost on this route
    "avg_transit_days": float,  // Mean transit time
    "sample_size": int          // Number of historical orders
  }
}
```

### Example
```json
{
  "South_Midwest_Flight": {
    "failure_rate": 0.38,       // 38% failure rate
    "avg_transit_days": 2.1,    // ~2 days average
    "sample_size": 145          // 145 orders in dataset
  },
  "West_East_Road": {
    "failure_rate": 0.62,       // 62% failure (high-risk!)
    "avg_transit_days": 7.8,    // ~8 days average
    "sample_size": 89
  }
}
```

### Usage in KPIs
- **TransitHoursKPI:** Threshold = `(avg_transit_days * 24) + 24` hours buffer
  - South_Midwest_Flight: (2.1 * 24) + 24 = **74.4h threshold**
  - West_East_Road: (7.8 * 24) + 24 = **211.2h threshold**
- **RouteRiskKPI:** Breaches if `failure_rate > 0.5`
  - South_Midwest_Flight: 0.38 → Safe
  - West_East_Road: 0.62 → **High Risk**

**75 total routes** in dataset, covering all region+mode combinations.

---

## Customer Statistics (`customer_stats.json`)

**Generated from enriched CSV** for agent context on customer behavior patterns.

### Schema by Rating (1-5)
```json
{
  "1": {  // Low-satisfaction customers
    "avg_care_calls": 4.2,
    "complaint_rate": 0.89,
    "avg_prior_purchases": 2.1
  },
  "5": {  // High-satisfaction customers
    "avg_care_calls": 1.8,
    "complaint_rate": 0.12,
    "avg_prior_purchases": 5.7
  }
}
```

### Usage
**CustomerAgent** uses this to tailor communication:
- Rating 1-2: More empathy, proactive refund offer
- Rating 4-5: Brief update, reschedule option sufficient

---

## Data Quality

### Validation Checks
✅ No nulls in critical timestamp fields (Order_Date, Ship_Date, Promised_Date)  
✅ Logical date sequences (Order ≤ Ship ≤ Arrival ≤ Delivery)  
✅ Realistic transit times per mode (Flight: 1-4d, Road: 3-9d, Ship: 5-12d)  
✅ Status consistency (Delivered ↔ Actual_Delivery_Date exists)  
✅ 28 columns in final CSV (12 original + 16 enriched)

### Known Limitations
⚠️ Synthetic data - not real customer/logistics data  
⚠️ Simplified US regions (5 regions vs 50 states)  
⚠️ No external factors (weather, holidays, carrier strikes)  
⚠️ Mock delay causes (not from actual shipment tracking)

---

## Regenerate Statistics

```bash
# Route stats (used by KPIs)
python -m src.data_preprocessing.route_stats_generator --update

# Customer stats (used by agent)
python -m src.data_preprocessing.customer_stats_generator
```

Both read from `Enriched_Data_Final.csv`.
