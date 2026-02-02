"""
Customer Statistics Generator

Generates customer_stats.json from enriched CSV for use by agent tools.
Groups stats by customer_rating (1-5).

Usage:
    python -m src.data_preprocessing.customer_stats_generator [--update]
"""
import argparse
import json
from pathlib import Path
import pandas as pd


DEFAULT_CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "Celonis_Garage_Enriched_Data_Final.csv"
DEFAULT_JSON_PATH = Path(__file__).resolve().parents[2] / "data" / "customer_stats.json"


def generate_customer_stats(csv_path: Path) -> dict:
    """
    Generate customer stats grouped by rating (1-5).
    
    Returns: {rating: {avg_care_calls, complaint_rate, avg_prior_purchases, sample_size}}
    """
    df = pd.read_csv(csv_path)
    
    stats = {}
    for rating in range(1, 6):
        group = df[df['Customer_rating'] == rating]
        
        if len(group) == 0:
            continue
        
        # Complaint rate = ticket raised or late delivery
        complaint_rate = 0.0
        if 'Ticket_Raised' in group.columns:
            complaint_rate = group['Ticket_Raised'].mean()
        elif 'Reached.on.Time_Y.N' in group.columns:
            complaint_rate = 1.0 - group['Reached.on.Time_Y.N'].mean()
        
        stats[str(rating)] = {
            "avg_care_calls": round(group['Customer_care_calls'].mean(), 1),
            "complaint_rate": round(complaint_rate, 2),
            "avg_prior_purchases": round(group['Prior_purchases'].mean(), 1),
            "sample_size": len(group)
        }
    
    return stats


def main():
    parser = argparse.ArgumentParser(description="Generate customer statistics by rating")
    parser.add_argument("--update", action="store_true", help="Force recompute")
    args = parser.parse_args()
    
    if DEFAULT_JSON_PATH.exists() and not args.update:
        print(f"Customer stats exist at {DEFAULT_JSON_PATH}")
        print("Use --update to recompute")
        return
    
    print(f"Generating from {DEFAULT_CSV_PATH}...")
    stats = generate_customer_stats(DEFAULT_CSV_PATH)
    
    with DEFAULT_JSON_PATH.open("w") as f:
        json.dump(stats, f, indent=2, sort_keys=True)
    
    print(f"Saved stats for {len(stats)} rating groups to {DEFAULT_JSON_PATH}")
    for rating, data in sorted(stats.items()):
        print(f"  Rating {rating}: {data['sample_size']} customers, {data['avg_care_calls']} avg calls")


if __name__ == "__main__":
    main()
