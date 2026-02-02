# Data Directory

Datasets for the Proactive Logistics Agent.

## Files

| File | Rows | Columns | Purpose |
|------|------|---------|---------|
| `Original_data.csv` | 10,999 | 12 | Kaggle source dataset |
| `Celonis_Garage_Enriched_Data_Final.csv` | 10,999 | 28 | Enriched with 16 synthetic columns |
| `route_stats.json` | 75 routes | 3 fields | Route performance for KPI thresholds |

## Data Pipeline

```
Original_data.csv (12 cols)
        │
        ▼  Gemini Pro enrichment
Celonis_Garage_Enriched_Data_Final.csv (28 cols)
        │
        ▼  route_stats_generator.py
route_stats.json (75 routes)
        │
        ▼  loaded by RiskEngine
KPI dynamic thresholds
```

## Enrichment Details

**Tool:** Gemini Pro LLM  
**Prompts:** `src/data_preprocessing/enrichment_prompts.md`  
**Validation:** `src/data_preprocessing/validate_enrichment.ipynb`

### Original Columns (12)
`ID`, `Warehouse_block`, `Mode_of_Shipment`, `Customer_care_calls`, `Customer_rating`, `Cost_of_the_Product`, `Prior_purchases`, `Product_importance`, `Gender`, `Discount_offered`, `Weight_in_gms`, `Reached.on.Time_Y.N`

### Added Columns (16)
| Category | Columns | Count |
|----------|---------|-------|
| Timestamps | `Order_Date`, `Promised_Date`, `Ship_Date`, `Destination_Arrival_Date`, `Actual_Delivery_Date` | 5 |
| Regions | `Origin_Region`, `Destination_Region` | 2 |
| Status | `Final_Status`, `Delay_Cause` | 2 |
| Payment | `Payment_Status`, `Payment_Mode` | 2 |
| Customer | `Customer_type` | 1 |
| Support | `Ticket_Raised` | 1 |
| Pre-calc | `Gap_Shipping_Days`, `Gap_Transit_Days`, `Gap_SLA_Days` | 3 |
| **Total** | | **16** |

## Route Stats

Generated from enriched CSV, used by KPIs for route-specific thresholds.

```json
{
  "South_Midwest_Flight": {
    "failure_rate": 0.38,
    "avg_transit_days": 2.1,
    "sample_size": 145
  }
}
```

**Regenerate:**
```bash
python -m src.data_preprocessing.route_stats_generator --update
```
