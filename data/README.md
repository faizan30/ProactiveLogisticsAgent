# Data Directory

Contains datasets for the Proactive Logistics Agent.

## Files

| File | Rows | Columns | Description |
|------|------|---------|-------------|
| `Original_data.csv` | 10,999 | 12 | Kaggle Customer Analytics source |
| `Celonis_Garage_Enriched_Data_Final.csv` | 10,999 | 28 | + 16 synthetic columns |
| `route_stats.json` | - | - | Pre-computed route performance statistics |

## Data Enrichment

The original Kaggle dataset lacked timestamps and routing information. We used **Gemini Pro** to generate 15 synthetic columns.

**Full documentation:** [`src/data_preprocessing/`](../src/data_preprocessing/)

- Prompts: `src/data_preprocessing/enrichment_prompts.md`
- Stats generator: `src/data_preprocessing/route_stats_generator.py`
- Validation notebook: `src/data_preprocessing/validate_enrichment.ipynb`

## Column Summary

### Original (12 columns)
`ID`, `Warehouse_block`, `Mode_of_Shipment`, `Customer_care_calls`, `Customer_rating`, `Cost_of_the_Product`, `Prior_purchases`, `Product_importance`, `Gender`, `Discount_offered`, `Weight_in_gms`, `Reached.on.Time_Y.N`

### Added (15 columns)
| Category | Columns |
|----------|---------|
| Timestamps | `Order_Date`, `Promised_Date`, `Ship_Date`, `Destination_Arrival_Date`, `Actual_Delivery_Date` |
| Regions | `Origin_Region`, `Destination_Region` |
| Status | `Final_Status`, `Delay_Cause` |
| Payment | `Payment_Status`, `Payment_Mode` |
| Support | `Ticket_Raised` |
| Customer | `Customer_type` |
| Pre-calc | `Gap_Shipping_Days`, `Gap_Transit_Days`, `Gap_SLA_Days` |

## Regenerate Route Stats

```bash
python -m src.data_preprocessing.route_stats_generator --update
```
