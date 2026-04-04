import subprocess
from concurrent.futures import ThreadPoolExecutor

QUARTERS = ["Jan-Mar", "Apr-Jun", "Jul-Sep", "Oct-Dec"]
YEARS = range(2011, 2026)
EXTRA_QUARTERS = ["Jan-Mar 2026"]

def run_aum(quarter_str):
    print(f"Starting fetch for {quarter_str}...")
    try:
        # Run with head 1 to verify fetch and cache while keeping output short
        res = subprocess.run(
            ["uv", "run", "mfa", "aum", quarter_str, "--top", "1"],
            capture_output=True,
            text=True
        )
        if res.returncode == 0:
            print(f"Success: {quarter_str}")
        else:
            print(f"Failed: {quarter_str}\n{res.stderr}")
    except Exception as e:
        print(f"Error: {e}")

def main():
    all_quarters = []
    # 2011-2025
    for year in YEARS:
        for q in QUARTERS:
            all_quarters.append(f"{q} {year}")
    
    # 2026
    all_quarters.extend(EXTRA_QUARTERS)

    print(f"Planning to fetch {len(all_quarters)} quarters...")

    # Run in parallel
    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(run_aum, all_quarters)

if __name__ == "__main__":
    main()
