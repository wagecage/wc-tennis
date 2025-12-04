import sqlite3
import pandas as pd
import numpy as np
import json
import re
from datetime import datetime, timedelta

# --- CONFIGURATION ---
DB_FILE = "tennis_data.db"
OUTPUT_FILE = "players_live.json"
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

def save_state():
    print("--- GENERATING LIVE STATE (FINAL FIX) ---")
    conn = sqlite3.connect(DB_FILE)
    
    # 1. LOAD DATA
    query = """
        SELECT tourney_date, winner_name, loser_name, surface, score, 
               w_svpt, w_1stWon, w_2ndWon, l_svpt, l_1stWon, l_2ndWon,
               winner_ht, loser_ht, winner_hand, loser_hand,
               w_bpSaved, w_bpFaced, l_bpSaved, l_bpFaced
        FROM matches ORDER BY tourney_date ASC, match_num ASC
    """
    df = pd.read_sql(query, conn)
    
    # FIX: Handle mixed date formats (Timestamps vs Strings)
    df['tourney_date'] = pd.to_datetime(df['tourney_date'], format='mixed', errors='coerce')
    
    # Force numeric types (coercing errors to NaN)
    cols_to_fix = ['w_bpSaved', 'w_bpFaced', 'l_bpSaved', 'l_bpFaced', 'w_svpt', 'l_svpt']
    for c in cols_to_fix:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

    player_stats = {}
    
    def get_player(name):
        if name not in player_stats:
            player_stats[name] = {
                'elo': 1500,
                'matches': 0,
                'wins_last_5': [],
                'wins_last_20': [],
                'match_dates': [],
                'surface_wins': {'Hard':0, 'Clay':0, 'Grass':0, 'Carpet':0},
                'surface_loss': {'Hard':0, 'Clay':0, 'Grass':0, 'Carpet':0},
                'serve_pts_won': [],
                'return_pts_won': [],
                'comebacks_attempted': 0,
                'comebacks_won': 0,
                'height': 185, 'hand': 'R',
                'bp_saved_total': 0, 'bp_faced_total': 0
            }
        return player_stats[name]

    print(f"Replaying {len(df)} matches...")
    
    for _, row in df.iterrows():
        w_name = row['winner_name']
        l_name = row['loser_name']
        date = row['tourney_date']
        
        if pd.isna(date): continue # Skip rows with bad dates
        
        w = get_player(w_name)
        l = get_player(l_name)
        
        # 1. Update Traits
        if row['winner_ht'] > 0: w['height'] = row['winner_ht']
        if row['loser_ht'] > 0: l['height'] = row['loser_ht']
        if row['winner_hand']: w['hand'] = row['winner_hand']
        if row['loser_hand']: l['hand'] = row['loser_hand']
        
        # 2. Update Elo
        prob_w = get_elo_win_prob(w['elo'], l['elo'])
        w['elo'] = update_elo(w['elo'], 1, prob_w, 30)
        l['elo'] = update_elo(l['elo'], 0, (1-prob_w), 30)
        
        # 3. Update Form
        w['matches'] += 1; l['matches'] += 1
        w['match_dates'].append(date); l['match_dates'].append(date)
        w['wins_last_5'].append(1); l['wins_last_5'].append(0)
        w['wins_last_20'].append(1); l['wins_last_20'].append(0)
        
        # 4. Surface
        if row['surface'] in w['surface_wins']:
            w['surface_wins'][row['surface']] += 1
            l['surface_loss'][row['surface']] += 1

        # 5. Update Clutch (BP stats)
        if row['w_bpFaced'] > 0: 
            w['bp_saved_total'] += row['w_bpSaved']
            w['bp_faced_total'] += row['w_bpFaced']
        if row['l_bpFaced'] > 0:
            l['bp_saved_total'] += row['l_bpSaved']
            l['bp_faced_total'] += row['l_bpFaced']

        # 6. Update Serve
        if row['w_svpt'] > 0 and row['l_svpt'] > 0:
            w_s = (row['w_1stWon'] + row['w_2ndWon']) / row['w_svpt']
            l_s = (row['l_1stWon'] + row['l_2ndWon']) / row['l_svpt']
            w['serve_pts_won'].append(w_s); w['return_pts_won'].append(1 - l_s)
            l['serve_pts_won'].append(l_s); l['return_pts_won'].append(1 - w_s)

        # 7. Cleanup
        for p in [w, l]:
            if len(p['wins_last_5']) > 5: p['wins_last_5'].pop(0)
            if len(p['wins_last_20']) > 20: p['wins_last_20'].pop(0)
            if len(p['serve_pts_won']) > ROLLING_WINDOW: 
                p['serve_pts_won'].pop(0); p['return_pts_won'].pop(0)
            # Keep dates fresh
            p['match_dates'] = [d for d in p['match_dates'] if (date - d).days <= 45]
            
        fsl = parse_first_set_loser(row['score'])
        if fsl == 'W': w['comebacks_attempted']+=1; w['comebacks_won']+=1
        elif fsl == 'L': l['comebacks_attempted']+=1

    # --- FINAL EXPORT ---
    print("Finalizing live stats...")
    final_export = {}
    now = datetime.now()
    
    for name, stats in player_stats.items():
        if stats['matches'] < 5: continue
        
        recent_matches = sum(1 for d in stats['match_dates'] if (now - d).days <= 14)
        
        if stats['bp_faced_total'] > 10:
            clutch = stats['bp_saved_total'] / stats['bp_faced_total']
        else:
            clutch = 0.60
        
        s_avg = np.mean(stats['serve_pts_won']) if stats['serve_pts_won'] else 0.60
        r_avg = np.mean(stats['return_pts_won']) if stats['return_pts_won'] else 0.35
        
        final_export[name] = {
            'elo': stats['elo'],
            'matches': stats['matches'],
            'form_20': np.mean(stats['wins_last_20']) if stats['wins_last_20'] else 0.5,
            'momentum_5': np.mean(stats['wins_last_5']) if stats['wins_last_5'] else 0.5,
            'serve': float(s_avg),
            'return': float(r_avg),
            'comeback': stats['comebacks_won']/stats['comebacks_attempted'] if stats['comebacks_attempted']>0 else 0.0,
            'pressure': clutch,
            'fatigue': recent_matches,
            'height': stats['height'],
            'hand': 1 if stats['hand'] == 'L' else 0,
            'surface_hard': stats['surface_wins']['Hard'] / (stats['surface_wins']['Hard'] + stats['surface_loss']['Hard']) if (stats['surface_wins']['Hard'] + stats['surface_loss']['Hard']) > 0 else 0.5,
            'surface_clay': stats['surface_wins']['Clay'] / (stats['surface_wins']['Clay'] + stats['surface_loss']['Clay']) if (stats['surface_wins']['Clay'] + stats['surface_loss']['Clay']) > 0 else 0.5,
            'surface_grass': stats['surface_wins']['Grass'] / (stats['surface_wins']['Grass'] + stats['surface_loss']['Grass']) if (stats['surface_wins']['Grass'] + stats['surface_loss']['Grass']) > 0 else 0.5
        }

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(final_export, f)
        
    print(f"SUCCESS: Saved live profile for {len(final_export)} players.")
    
    if "Jannik Sinner" in final_export:
        print(f"VERIFY Sinner Pressure: {final_export['Jannik Sinner']['pressure']:.1%}")

if __name__ == "__main__":
    save_state()