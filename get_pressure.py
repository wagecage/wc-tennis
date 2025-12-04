import pandas as pd
import requests
from io import BytesIO
import json

# --- CONFIGURATION ---
BASE_URL = "https://raw.githubusercontent.com/JeffSackmann/tennis_MatchChartingProject/master"
STATS_URL = f"{BASE_URL}/charting-m-stats-Overview.csv"
OUTPUT_FILE = "player_pressure_stats.json"

def get_pressure_stats():
    print("--- DOWNLOADING PRESSURE STATS (FINAL) ---")
    
    # 1. Load Stats
    print("Fetching Stats Overview...")
    try:
        r_s = requests.get(STATS_URL)
        r_s.raise_for_status()
        df_stats = pd.read_csv(BytesIO(r_s.content), encoding='ISO-8859-1')
        print(f"   -> Loaded {len(df_stats)} stat rows.")
    except Exception as e:
        print(f"Error downloading stats: {e}")
        return

    # 2. IDENTIFY COLUMNS
    # Based on your debug output, we know these match exactly:
    player_col = 'player'
    saved_col = 'bp_saved'
    faced_col = 'bk_pts'
    
    # 3. AGGREGATE STATS
    print("Aggregating stats by player...")
    
    player_pressure = {}
    
    for _, row in df_stats.iterrows():
        p_name = row[player_col]
        
        # Skip invalid names
        if pd.isna(p_name) or not isinstance(p_name, str):
            continue
            
        # Get Stats (Handle potential non-numeric data gracefully)
        try:
            saved = float(row[saved_col])
            faced = float(row[faced_col])
        except (ValueError, TypeError):
            continue
            
        if p_name not in player_pressure:
            player_pressure[p_name] = {'saved': 0, 'faced': 0}
            
        player_pressure[p_name]['saved'] += saved
        player_pressure[p_name]['faced'] += faced

    # 4. CALCULATE & SAVE
    final_output = {}
    valid_players = 0
    
    # Filter: Minimum 20 break points faced to be statistically significant
    MIN_BP_FACED = 20
    
    for p, stats in player_pressure.items():
        if stats['faced'] >= MIN_BP_FACED:
            save_pct = stats['saved'] / stats['faced']
            final_output[p] = round(save_pct, 3)
            valid_players += 1
            
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(final_output, f)
        
    print(f"\n[DONE] Database built for {valid_players} players.")
    print(f"Saved to: {OUTPUT_FILE}")
    
    # VERIFICATION
    # Check for a top player to ensure math is right
    check_list = ["Novak Djokovic", "Rafael Nadal", "Roger Federer", "Jannik Sinner", "Carlos Alcaraz"]
    print("\n--- VERIFICATION CHECKS ---")
    found_any = False
    for p in check_list:
        if p in final_output:
            print(f"{p}: Saved {final_output[p]*100:.1f}% of Break Points")
            found_any = True
            
    if not found_any:
        print("Warning: Big names not found. Check if names match exactly (e.g. 'Novak Djokovic').")

if __name__ == "__main__":
    get_pressure_stats()