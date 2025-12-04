import pandas as pd
import requests
from io import BytesIO
import numpy as np

# --- CONFIGURATION ---
# We now list ALL three files to get the complete history
MCP_URLS = [
    "https://raw.githubusercontent.com/JeffSackmann/tennis_MatchChartingProject/master/charting-m-points-2020s.csv",
    "https://raw.githubusercontent.com/JeffSackmann/tennis_MatchChartingProject/master/charting-m-points-2010s.csv",
    "https://raw.githubusercontent.com/JeffSackmann/tennis_MatchChartingProject/master/charting-m-points-to-2009.csv"
]
OUTPUT_FILE = "advanced_point_stats.csv"

def is_break_point(score):
    """
    Parses strings like '15-40', '40-AD' to determine if it's a Break Point.
    Assumption: Score is formatted as 'Server-Receiver'.
    """
    if not isinstance(score, str): return 0
    
    # Clean up standard variations
    score = score.replace("A", "AD")
    
    parts = score.split("-")
    if len(parts) != 2: return 0
    
    svr, ret = parts[0], parts[1]
    
    # Standard Break Points (Server score is low, Returner is 40)
    if ret == "40" and svr in ["0", "15", "30"]:
        return 1
        
    # Advantage Receiver (Ad-Out)
    if ret == "AD" and svr == "40":
        return 1
        
    return 0

def parse_mcp_data():
    print("--- DOWNLOADING & COMBINING POINT DATA ---")
    
    all_dfs = []
    
    for url in MCP_URLS:
        filename = url.split("/")[-1]
        print(f"Fetching {filename}...")
        try:
            response = requests.get(url)
            response.raise_for_status()
            
            # Read individual decade file
            # low_memory=False handles mixed types in large files
            df_part = pd.read_csv(BytesIO(response.content), encoding='ISO-8859-1', low_memory=False)
            all_dfs.append(df_part)
            print(f"   -> Loaded {len(df_part)} points.")
            
        except Exception as e:
            print(f"   [ERROR] Failed to download {filename}: {e}")
            return

    # Combine into one massive DataFrame
    print("Concatenating files...")
    df = pd.concat(all_dfs, ignore_index=True)
    print(f"TOTAL POINTS LOADED: {len(df)}")
    
    # --- 1. FEATURE ENGINEERING: CREATE 'isBP' ---
    print("Calculating Break Points from Score... (This takes time)")
    
    if 'Pts' in df.columns:
        # We apply the logic to identify rows that are Break Points
        df['isBP'] = df['Pts'].apply(is_break_point)
    else:
        print("Error: 'Pts' column missing. Cannot calculate stats.")
        return

    # --- 2. AGGREGATE STATS ---
    print("Aggregating Match Stats...")
    
    stats_list = []
    
    # Group by match_id to process each match individually
    grouped = df.groupby('match_id')
    
    count = 0
    for match_id, match_points in grouped:
        
        # Filter for Break Points to speed up processing
        bp_points = match_points[match_points['isBP'] == 1]
        
        # Svr column: 1 = Player 1 serving, 2 = Player 2 serving
        # isSvrWinner: 1 = Server won point, 0 = Receiver won point
        
        # P1 FACING BP (P1 Serving, P2 Returning)
        p1_serving_bp = bp_points[bp_points['Svr'] == 1]
        p1_faced = len(p1_serving_bp)
        p1_saved = len(p1_serving_bp[p1_serving_bp['isSvrWinner'] == 1]) # Server won = Saved
        
        # P2 FACING BP (P2 Serving, P1 Returning)
        p2_serving_bp = bp_points[bp_points['Svr'] == 2]
        p2_faced = len(p2_serving_bp)
        p2_saved = len(p2_serving_bp[p2_serving_bp['isSvrWinner'] == 1])
        
        # Pressure Index (Total BPs faced in the match)
        pressure_idx = p1_faced + p2_faced
        
        stats_list.append({
            'match_id': match_id,
            'p1_bp_faced': p1_faced,
            'p1_bp_saved': p1_saved,
            'p2_bp_faced': p2_faced,
            'p2_bp_saved': p2_saved,
            'pressure_index': pressure_idx
        })
        
        count += 1
        if count % 5000 == 0: print(f"Processed {count} matches...")

    # --- 3. SAVE ---
    print(f"Saving records to {OUTPUT_FILE}...")
    stats_df = pd.DataFrame(stats_list)
    stats_df.to_csv(OUTPUT_FILE, index=False)
    print(f"Done! {OUTPUT_FILE} is ready.")

if __name__ == "__main__":
    parse_mcp_data()