# Data Enrichment Prompts

Prompts and rules used with **Gemini Pro** to generate synthetic columns for the logistics simulation.

## Why Gemini Pro?

- **Long context window**: Process full dataset schema in single prompt
- **Domain accuracy**: Strong understanding of logistics/e-commerce patterns
- **Structured output**: Reliable CSV generation

## Inspiration

Schema patterns inspired by [Superstore Dataset 2015-2018](https://www.kaggle.com/datasets/ankumagawa/dataset-superstore-20152018) (structure only, not values).

---

## Input Schema (12 columns from Kaggle)

```
ID, Warehouse_block, Mode_of_Shipment, Customer_care_calls, Customer_rating,
Cost_of_the_Product, Prior_purchases, Product_importance, Gender,
Discount_offered, Weight_in_gms, Reached.on.Time_Y.N
```

## Output Schema (16 new columns)

| Column | Type | Actual Values |
|--------|------|---------------|
| `Order_Date` | datetime | Distributed across 30-day window (Sept 1-30, 2024) |
| `Promised_Date` | datetime | Order_Date + 7-14 days (varies by Mode_of_Shipment) |
| `Ship_Date` | datetime | Order_Date + 1-3 days |
| `Destination_Arrival_Date` | datetime | Ship_Date + transit time (mode-dependent) |
| `Actual_Delivery_Date` | datetime | Arrival + 1 day; ~18% NULL for undelivered/ghost scenarios |
| `Origin_Region` | string | North, South, East, West, Midwest |
| `Destination_Region` | string | North, South, East, West, Midwest |
| `Customer_type` | string | Consumer (~48%), Corporate (~43%), Home Office (~9%) |
| `Final_Status` | string | Delivered, In-Transit, Pending, Returned |
| `Delay_Cause` | string | Carrier, Weather, Customs, Warehouse, None |
| `Payment_Status` | string | Paid (~78%), Refunded (~18%), COD (~4%) |
| `Payment_Mode` | string | Credit Card, Debit Card, COD, PayPal, UPI |
| `Ticket_Raised` | int (0/1) | 1 if escalated (~41% of orders) |
| `Gap_Shipping_Days` | int | Ship_Date - Order_Date |
| `Gap_Transit_Days` | int | Arrival_Date - Ship_Date |
| `Gap_SLA_Days` | int | Actual_Delivery_Date - Promised_Date (negative = early) |

---

## Enrichment Prompt Template

```
You are a logistics data engineer. I have an e-commerce orders dataset with the following columns:

[PASTE ORIGINAL 12 COLUMNS]

I need you to enrich this dataset by adding new columns for a supply chain simulation. 
Follow these rules exactly:

### Timestamp Generation
1. Order_Date: Distribute across September 1-30, 2024
2. Promised_Date: Order_Date + random(7-14) days, adjusted by shipment mode
3. Ship_Date: Order_Date + random(1-3) days
4. Destination_Arrival_Date: Ship_Date + transit time by mode
5. Actual_Delivery_Date: Arrival + 1 day
   - ~18% NULL (undelivered/ghost delivery scenarios)

### Region Assignment
- Origin_Region: Random from [North, South, East, West, Midwest]
- Destination_Region: Random from [North, South, East, West, Midwest]

### Customer Segmentation
- Customer_type: Consumer (~48%), Corporate (~43%), Home Office (~9%)

### Status Fields
- Final_Status: Based on date completeness (Delivered, In-Transit, Pending, Returned)
- Delay_Cause: If late, random from [Carrier, Weather, Customs, Warehouse]

### Payment Fields
- Payment_Status: Paid (~78%), Refunded (~18%), COD (~4%)
- Payment_Mode: Random from [Credit Card, Debit Card, COD, PayPal, UPI]

### Support Flag
- Ticket_Raised: 0/1 integer (~41% raised)

### Pre-calculated Gaps
- Gap_Shipping_Days: Ship_Date - Order_Date
- Gap_Transit_Days: Arrival_Date - Ship_Date
- Gap_SLA_Days: Actual_Delivery_Date - Promised_Date

Output as CSV with all 28 columns. Maintain original row order.
```

---

## Verification Checklist

After generation, verify:
- [ ] All 28 columns present (12 original + 16 enriched)
- [ ] ~18% Actual_Delivery_Date NULL (undelivered orders)
- [ ] Date logic consistent (Order < Ship < Arrival < Delivery)
- [ ] Regions from valid set: North, South, East, West, Midwest
- [ ] Customer_type: Consumer, Corporate, Home Office
- [ ] Payment_Status: Paid (~78%), Refunded (~18%), COD (~4%)

Use `src/data_preprocessing/validate_enrichment.ipynb` to run these checks.

---

## Route Stats Generation

After enrichment, generate route statistics for KPI dynamic thresholds:

```bash
python -m src.data_preprocessing.route_stats_generator --update
```

This creates `data/route_stats.json` with failure rates and average transit times per route+mode combination, used by `TransitHoursKPI` and `RouteRiskKPI`.
