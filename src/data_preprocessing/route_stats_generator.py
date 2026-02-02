"""
Route Statistics Generator

Generates route_stats.json from enriched CSV for use by RiskEngine.

Usage:
    python -m src.data_preprocessing.route_stats_generator [--update]
"""
import argparse
import json
from pathlib import Path
from typing import Dict
import pandas as pd


DEFAULT_CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "Celonis_Garage_Enriched_Data_Final.csv"
DEFAULT_JSON_PATH = Path(__file__).resolve().parents[2] / "data" / "route_stats.json"


def generate_route_stats(csv_path: Path) -> Dict:
    """
    Generate route stats from enriched CSV.
    
    Route key: "{origin}_{destination}_{mode}"
    Returns: {route_key: {failure_rate, avg_transit_days, sample_size}}
    """
    df = pd.read_csv(csv_path)
    
    # Convert dates
    for col in ['Ship_Date', 'Actual_Delivery_Date']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    
    stats = {}
    groups = df.groupby(['Origin_Region', 'Destination_Region', 'Mode_of_Shipment'])
    
    for (origin, dest, mode), group in groups:
        key = f"{origin}_{dest}_{mode}"
        
        # Failure rate from on-time flag
        if 'Reached.on.Time_Y.N' in group.columns:
            failure_rate = 1.0 - group['Reached.on.Time_Y.N'].mean()
        else:
            failure_rate = 0.0
        
        # Average transit days
        delivered = group[
            pd.notna(group['Actual_Delivery_Date']) & 
            pd.notna(group['Ship_Date'])
        ]
        if not delivered.empty:
            avg_transit = (delivered['Actual_Delivery_Date'] - delivered['Ship_Date']).dt.days.mean()
        else:
            avg_transit = 3.0
        
        stats[key] = {
            "failure_rate": round(failure_rate, 2),
            "avg_transit_days": max(round(avg_transit, 1), 0.5),  # Min 0.5 days
            "sample_size": len(group)
        }
    
    return stats


def main():
    parser = argparse.ArgumentParser(description="Generate route statistics")
    parser.add_argument("--update", action="store_true", help="Force recompute")
    args = parser.parse_args()
    
    if DEFAULT_JSON_PATH.exists() and not args.update:
        print(f"Route stats exist at {DEFAULT_JSON_PATH}")
        print("Use --update to recompute")
        return
    
    print(f"Generating from {DEFAULT_CSV_PATH}...")
    stats = generate_route_stats(DEFAULT_CSV_PATH)
    
    with DEFAULT_JSON_PATH.open("w") as f:
        json.dump(stats, f, indent=2, sort_keys=True)
    
    print(f"Saved {len(stats)} routes to {DEFAULT_JSON_PATH}")


if __name__ == "__main__":
    main()
