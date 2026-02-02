# Data Preprocessing

This module contains artifacts and scripts for dataset preparation.

## Contents

| File | Purpose |
|------|---------|
| `enrichment_prompts.md` | Gemini Pro prompts used for synthetic data generation |
| `route_stats_generator.py` | Standalone script to generate route performance statistics |
| `validate_enrichment.ipynb` | Jupyter notebook to validate enriched data |

## Offline vs Online Transformations

| Type | When | What |
|------|------|------|
| **Offline** | One-time, before deployment | Enrich CSV with 15 synthetic columns using Gemini Pro |
| **Online** | At runtime | Time-travel masking, KPI calculation, signal detection |

## Usage

### Regenerate Route Statistics

```bash
# Check if exists (won't overwrite)
python -m src.data_preprocessing.route_stats_generator

# Force recompute
python -m src.data_preprocessing.route_stats_generator --update
```

### Re-enrich Dataset

If you need to regenerate the enriched dataset:
1. Review `enrichment_prompts.md` for the Gemini Pro prompt
2. Run prompt against `data/Original_data.csv`
3. Save output as `data/Celonis_Garage_Enriched_Data_Final.csv`

## See Also

- `data/README.md` - Dataset documentation
- `documentation/Architecture.md` Section 7 - Data simulation design
