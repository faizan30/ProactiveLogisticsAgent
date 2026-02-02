"""
Route Statistics Generator

Standalone script to generate route performance statistics from enriched CSV.
Output: data/route_stats.json

Usage:
    python -m src.data_preprocessing.route_stats_generator [--update]
    
Options:
    --update    Force recompute even if route_stats.json exists
"""
import argparse
import json
from pathlib import Path
from typing import Dict
import pandas as pd


DEFAULT_CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "Celonis_Garage_Enriched_Data_Final.csv"
DEFAULT_JSON_PATH = Path(__file__).resolve().parents[2] / "data" / "route_stats.json"


def generate_route_stats(df: pd.DataFrame) -> Dict:
    """
    Generate route performance statistics from enriched dataset.
    
    Groups by (Origin_Region, Destination_Region, Mode_of_Shipment) and calculates:
    - failure_rate: 1 - on_time_rate
    - avg_transit_days: mean transit time for delivered orders
    - sample_size: number of orders in route
    
    Args:
        df: DataFrame with enriched order data
        
    Returns:
        Dict with route keys (origin_dest_mode) -> stats
    """
    stats = {}
    
    # Ensure date columns are datetime
    for col in ['Ship_Date', 'Actual_Delivery_Date']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    
    # Group by route
    groups = df.groupby(['Origin_Region', 'Destination_Region', 'Mode_of_Shipment'])
    
    for (origin, dest, mode), group in groups:
        key = f"{origin}_{dest}_{mode}"
        
        # Calculate failure rate from on-time flag
        if 'Reached.on.Time_Y.N' in group.columns:
            on_time_rate = group['Reached.on.Time_Y.N'].mean()
            failure_rate = 1.0 - float(on_time_rate)
        else:
            failure_rate = 0.0
        
        # Calculate average transit days for delivered orders
        delivered = group[
            pd.notna(group['Actual_Delivery_Date']) & 
            pd.notna(group['Ship_Date'])
        ]
        if not delivered.empty:
            avg_transit = (
                delivered['Actual_Delivery_Date'] - delivered['Ship_Date']
            ).dt.days.mean()
        else:
            avg_transit = 3.0  # Default
        
        stats[key] = {
            "failure_rate": float(round(failure_rate, 2)),
            "avg_transit_days": float(round(avg_transit, 1)),
            "sample_size": int(len(group))
        }
    
    return stats


def save_stats(stats: Dict, json_path: Path) -> None:
    """Save stats to JSON with atomic write."""
    json_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = json_path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, sort_keys=True)
    tmp_path.replace(json_path)
    print(f"Saved {len(stats)} routes to {json_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate route statistics")
    parser.add_argument("--update", action="store_true", help="Force recompute")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV_PATH, help="Input CSV path")
    parser.add_argument("--output", type=Path, default=DEFAULT_JSON_PATH, help="Output JSON path")
    args = parser.parse_args()
    
    # Check if already exists
    if args.output.exists() and not args.update:
        print(f"Route stats already exist at {args.output}")
        print("Use --update to force recompute")
        return
    
    # Load and process
    print(f"Loading {args.csv}...")
    df = pd.read_csv(args.csv)
    print(f"Loaded {len(df)} orders")
    
    print("Generating route statistics...")
    stats = generate_route_stats(df)
    
    save_stats(stats, args.output)
    print("Done!")


if __name__ == "__main__":
    main()
