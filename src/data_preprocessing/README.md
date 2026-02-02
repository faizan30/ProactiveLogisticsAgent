# Data Preprocessing

Offline scripts for dataset preparation.

## Contents

| File | Purpose |
|------|---------|
| `route_stats_generator.py` | Generate route_stats.json from enriched CSV |
| `enrichment_prompts.md` | Gemini Pro prompts for synthetic data |
| `validate_enrichment.ipynb` | Data quality validation notebook |

## How It Works

```
Enriched CSV  ──▶  route_stats_generator.py  ──▶  route_stats.json
                                                        │
                                                        ▼
                                               RiskEngine loads at startup
                                               for dynamic KPI thresholds
```

## Route Stats JSON

Route key format: `"{origin}_{destination}_{mode}"`

```json
{
  "South_Midwest_Flight": {
    "failure_rate": 0.38,
    "avg_transit_days": 2.1,
    "sample_size": 145
  }
}
```

Used by `TransitHoursKPI` and `RouteRiskKPI` for route-specific thresholds.

## Usage

```bash
# Generate (skips if exists)
python -m src.data_preprocessing.route_stats_generator

# Force regenerate
python -m src.data_preprocessing.route_stats_generator --update
```

## See Also

- `src/risk_detection/risk_engine.py` - Loads route_stats.json at line 25-31
- `src/risk_detection/kpis.py` - Uses route stats for dynamic thresholds
