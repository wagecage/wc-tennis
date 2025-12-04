import sqlite3
import pandas as pd
import numpy as np
import re

# --- CONFIGURATION ---
DB_FILE = "tennis_data.db"
ROLLING_WINDOW = 50

def get_elo_win_prob(elo_a, elo_b):
    return 1 / (1 + 10 ** ((elo_b - elo_a) / 400))

def update_elo(old_elo, actual_score, expected_score, k_factor=32):
    return old_elo + k_factor * (actual_score - expected_score)

def parse_first_set_loser(score_str):
    if not isinstance(score_str, str) or 'RET' in score_str or 'W/O' in score_str: return None
    match = re.match(r"(\d+)-(\d+)", score_str)
    if match:
        w, l = int(match.group(1)), int(match.group(2))
        return 'W' if l > w else 'L'
    return None

def build_features():
    print("--- REBUILDING TRAINING DATA (LEAKAGE FREE) ---")
    conn = sqlite3.connect(DB_FILE)
    
    # LOAD DATA (Including Break Point Stats)
    query = """
        SELECT 
            tourney_date, match_num, 
            winner_name, loser_name, 
            surface, score, tourney_level,
            w_svpt, w_1stWon, w_2ndWon, l_svpt, l_1stWon, l_2ndWon,
            winner_ht, loser_ht, winner_hand, loser_hand,
            w_bpSaved, w_bpFaced, l_bpSaved, l_bpFaced
        FROM matches 
        ORDER BY tourney_date ASC, match_num ASC
    """
    df = pd.read_sql(query, conn)
    df['tourney_date'] = pd.to_datetime(df['tourney_date'])
    
    player_stats = {}
    
    def get_player(name):
        if name not in player_stats:
            player_stats[name] = {
                'elo': 1500,
                'matches': 0,
                'wins_last_5': [],
                'wins_last_20': [],
                'match_dates': [],
                
                # PHYSICAL
                'height': 185, 'hand': 'R',
                
                # SERVE / RETURN LISTS
                'serve_pts_won': [],
                'return_pts_won': [],
                
                # CLUTCH STATS (ROLLING TOTALS)
                'bp_saved_total': 0,
                'bp_faced_total': 0,
                
                'comebacks_attempted': 0,
                'comebacks_won': 0
            }
        return player_stats[name]

    features_list = []
    print(f"Processing {len(df)} matches (Chronological)...")

    for index, row in df.iterrows():
        w_name = row['winner_name']
        l_name = row['loser_name']
        date = row['tourney_date']
        
        p1 = get_player(w_name)
        p2 = get_player(l_name)
        
        # 1. UPDATE TRAITS
        if row['winner_ht'] and row['winner_ht'] > 0: p1['height'] = row['winner_ht']
        if row['loser_ht'] and row['loser_ht'] > 0: p2['height'] = row['loser_ht']
        if row['winner_hand']: p1['hand'] = row['winner_hand']
        if row['loser_hand']: p2['hand'] = row['loser_hand']

        # 2. CALCULATE PRE-MATCH FEATURES (The Input)
        
        # Fatigue
        def get_fatigue(dates, current_date):
            return sum(1 for d in dates if (current_date - d).days <= 14)
        
        p1_fatigue = get_fatigue(p1['match_dates'], date)
        p2_fatigue = get_fatigue(p2['match_dates'], date)
        
        # Clutch (Rolling BP Save %)
        # Default to 60% if no data
        def get_clutch(p):
            if p['bp_faced_total'] < 10: return 0.60
            return p['bp_saved_total'] / p['bp_faced_total']

        p1_clutch = get_clutch(p1)
        p2_clutch = get_clutch(p2)

        # Standard Stats
        p1_form = np.mean(p1['wins_last_20']) if p1['wins_last_20'] else 0.5
        p2_form = np.mean(p2['wins_last_20']) if p2['wins_last_20'] else 0.5
        p1_mom = np.mean(p1['wins_last_5']) if p1['wins_last_5'] else 0.5
        p2_mom = np.mean(p2['wins_last_5']) if p2['wins_last_5'] else 0.5
        
        p1_srv = np.mean(p1['serve_pts_won']) if p1['serve_pts_won'] else 0.60
        p2_srv = np.mean(p2['serve_pts_won']) if p2['serve_pts_won'] else 0.60
        p1_ret = np.mean(p1['return_pts_won']) if p1['return_pts_won'] else 0.35
        p2_ret = np.mean(p2['return_pts_won']) if p2['return_pts_won'] else 0.35
        
        # SAVE ROW
        features_list.append({
            'date': date,
            'p1_elo': p1['elo'], 'p2_elo': p2['elo'],
            'p1_form': p1_form, 'p2_form': p2_form,
            'p1_momentum': p1_mom, 'p2_momentum': p2_mom,
            'p1_serve': p1_srv, 'p2_serve': p2_srv,
            'p1_return': p1_ret, 'p2_return': p2_ret,
            'p1_exp': np.log1p(p1['matches']), 'p2_exp': np.log1p(p2['matches']),
            
            # GOD MODE STATS (Leakage Free)
            'p1_pressure': p1_clutch, 'p2_pressure': p2_clutch,
            'fatigue_diff': p1_fatigue - p2_fatigue,
            'height_diff': p1['height'] - p2['height'],
            'p1_is_lefty': 1 if p1['hand'] == 'L' else 0,
            'p2_is_lefty': 1 if p2['hand'] == 'L' else 0,
            
            'surface': row['surface'],
            'target': 1
        })
        
        # 3. POST-MATCH UPDATES
        
        # Elo
        prob = get_elo_win_prob(p1['elo'], p2['elo'])
        p1['elo'] = update_elo(p1['elo'], 1, prob, 30)
        p2['elo'] = update_elo(p2['elo'], 0, 1-prob, 30)
        
        # Rolling Lists
        p1['matches'] += 1; p2['matches'] += 1
        p1['match_dates'].append(date); p2['match_dates'].append(date)
        p1['wins_last_5'].append(1); p2['wins_last_5'].append(0)
        p1['wins_last_20'].append(1); p2['wins_last_20'].append(0)
        
        # Update Clutch Stats (BP Saved/Faced)
        if not pd.isna(row['w_bpFaced']):
            p1['bp_saved_total'] += row['w_bpSaved']
            p1['bp_faced_total'] += row['w_bpFaced']
        if not pd.isna(row['l_bpFaced']):
            p2['bp_saved_total'] += row['l_bpSaved']
            p2['bp_faced_total'] += row['l_bpFaced']

        # Serve/Return
        if row['w_svpt'] > 0 and row['l_svpt'] > 0:
            p1_s = (row['w_1stWon'] + row['w_2ndWon']) / row['w_svpt']
            p2_s = (row['l_1stWon'] + row['l_2ndWon']) / row['l_svpt']
            p1['serve_pts_won'].append(p1_s); p1['return_pts_won'].append(1 - p2_s)
            p2['serve_pts_won'].append(p2_s); p2['return_pts_won'].append(1 - p1_s)

        # Truncate Lists
        for p in [p1, p2]:
            if len(p['wins_last_5']) > 5: p['wins_last_5'].pop(0)
            if len(p['wins_last_20']) > 20: p['wins_last_20'].pop(0)
            if len(p['serve_pts_won']) > ROLLING_WINDOW: 
                p['serve_pts_won'].pop(0); p['return_pts_won'].pop(0)
            # Keep match dates clean (last 30 days is safe)
            p['match_dates'] = [d for d in p['match_dates'] if (date - d).days <= 30]

        if index % 10000 == 0: print(f"   Processed {index} matches...")

    print("Saving Clean Training Data...")
    pd.DataFrame(features_list).to_csv('tennis_brain_features.csv', index=False)
    print("DONE. Leakage Removed.")

if __name__ == "__main__":
    build_features()