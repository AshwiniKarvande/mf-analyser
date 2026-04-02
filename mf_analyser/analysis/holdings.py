"""
Analysis logic for Mutual Fund portfolios.
Compare snapshots and aggregate by sector.
"""

from typing import Dict, List, Set, Tuple
import pandas as pd
from pathlib import Path
from mf_analyser.config import HOLDINGS_CACHE_DIR

def analyze_changes(old_data: Dict, new_data: Dict) -> Dict:
    """
    Compare two snapshots of holdings.
    Returns:
        added: List of new holdings
        exited: List of holdings present in old but not new
        increased: List of holdings where weight increased
        decreased: List of holdings where weight decreased
    """
    old_h = {h["name"]: h for h in old_data["holdings"]}
    new_h = {h["name"]: h for h in new_data["holdings"]}

    old_names = set(old_h.keys())
    new_names = set(new_h.keys())

    added_names = new_names - old_names
    exited_names = old_names - new_names
    common_names = old_names & new_names

    changes = {
        "added": [{"name": n, "weight": new_h[n]["weightage"], "sector": new_h[n]["sector"]} for n in sorted(added_names)],
        "exited": [{"name": n, "weight": old_h[n]["weightage"], "sector": old_h[n]["sector"]} for n in sorted(exited_names)],
        "increased": [],
        "decreased": []
    }

    for name in common_names:
        old_w = old_h[name]["weightage"]
        new_w = new_h[name]["weightage"]
        diff = new_w - old_w
        
        if abs(diff) > 0.01: # Filter tiny noise
            item = {
                "name": name,
                "old_weight": old_w,
                "new_weight": new_w,
                "diff": diff,
                "sector": new_h[name]["sector"]
            }
            if diff > 0:
                changes["increased"].append(item)
            else:
                changes["decreased"].append(item)

    # Sort weight changes by magnitude
    changes["increased"].sort(key=lambda x: x["diff"], reverse=True)
    changes["decreased"].sort(key=lambda x: x["diff"])

    return changes

def get_sector_allocation(data: Dict) -> pd.DataFrame:
    """Returns a DataFrame of sector-wise total weight."""
    holdings = data["holdings"]
    df = pd.DataFrame(holdings)
    if df.empty:
        return pd.DataFrame(columns=["sector", "weightage"])
    
    sector_df = df.groupby("sector")["weightage"].sum().reset_index()
    return sector_df.sort_values("weightage", ascending=False)

def get_snapshot_history(scheme_code: str) -> List[Path]:
    """Find all historical JSON snapshots for a scheme code, sorted by date."""
    code = str(scheme_code)
    files = list(HOLDINGS_CACHE_DIR.glob(f"{code}_*.json"))
    # Sort by filename which has YYYYMMDD suffix
    return sorted(files)

def get_top_holdings(data: Dict, top_n: int = 10) -> List[Dict]:
    """Returns top N holdings by weight."""
    return sorted(data["holdings"], key=lambda x: x["weightage"], reverse=True)[:top_n]
