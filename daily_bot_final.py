import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
from rapidfuzz import process, fuzz
import xgboost as xgb
import json
import numpy as np
import os

# --- CONFIGURATION ---
MODEL_FILE = "tennis_model_god_mode.json"
LIVE_STATS_FILE = "players_live.json"
SCHEDULE_URL = "https://www.tennisexplorer.com/matches/" 
OUTPUT_CSV = f"bets_{datetime.date.today()}.csv"

# Minimum confidence to verify a player name match (0-100)
NAME_MATCH_THRESHOLD = 85 

def load_system():
    print("Loading God Mode Engine...")
    model = xgb.XGBClassifier()
    model.load_model(MODEL_FILE)
    
    with open(LIVE_STATS_FILE, 'r') as f:
        live_stats = json.load(f)
        
    return model, live_stats

def get_schedule():
    print("Fetching today's schedule...")
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(SCHEDULE_URL, headers=headers)
        r.raise_for_status()
    except Exception as e:
        print(f"Connection Error: {e}")
        return []
        
    soup = BeautifulSoup(r.text, "html.parser")
    matches = []
    
    # TennisExplorer Parsing
    tables = soup.find_all("table", class_="result")
    current_surface = "Hard" # Default
    
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            # Detect Surface from Tournament Header
            if "head" in row.get("class", []):
                title = row.find("a").text.lower() if row.find("a") else ""
                if "clay" in title: current_surface = "Clay"
                elif "grass" in title: current_surface = "Grass"
                elif "indoors" in title: current_surface = "Hard"
                else: current_surface = "Hard"
            
            # Detect Match
            p_cells = row.find_all("td", class_="t-name")
            if len(p_cells) >= 2:
                p1 = p_cells[0].find("a").text.strip()
                p2 = p_cells[1].find("a").text.strip()
                # Check for odds to filter garbage matches (optional)
                matches.append({
                    "p1_web": p1, "p2_web": p2, "surface": current_surface
                })
    return matches

def fuzzy_match_player(name, db_names):
    # Returns (BestMatch, Score)
    match = process.extractOne(name, db_names, scorer=fuzz.token_set_ratio)
    return match if match and match[1] >= NAME_MATCH_THRESHOLD else (None, 0)

def predict_match_god_mode(model, live_stats, p1_name, p2_name, surface):
    p1 = live_stats[p1_name]
    p2 = live_stats[p2_name]
    
    # --- 1. CALCULATE DIFFS ---
    ht_diff = p1.get('height', 185) - p2.get('height', 185)
    fatigue_diff = p1.get('fatigue', 0) - p2.get('fatigue', 0)
    
    # --- 2. SURFACE ENCODING ---
    is_carpet = 1 if surface == 'Carpet' else 0
    is_clay = 1 if surface == 'Clay' else 0
    is_grass = 1 if surface == 'Grass' else 0
    is_hard = 1 if surface == 'Hard' else 0

    # --- 3. BUILD ROW (EXACT ORDER FROM V3 TRAINING) ---
    data = {
        'p1_elo': [p1['elo']], 'p2_elo': [p2['elo']],
        'p1_form': [p1['form_20']], 'p2_form': [p2['form_20']],
        'p1_momentum': [p1['momentum_5']], 'p2_momentum': [p2['momentum_5']],
        'p1_serve': [p1['serve']], 'p2_serve': [p2['serve']],
        'p1_return': [p1['return']], 'p2_return': [p2['return']],
        'p1_exp': [np.log1p(p1['matches'])], 'p2_exp': [np.log1p(p2['matches'])],
        
        # GOD MODE BLOCK
        'p1_pressure': [p1.get('pressure', 0.60)], 
        'p2_pressure': [p2.get('pressure', 0.60)],
        'fatigue_diff': [fatigue_diff],
        'height_diff': [ht_diff],
        'p1_is_lefty': [p1.get('hand', 0)],
        'p2_is_lefty': [p2.get('hand', 0)],
        
        # SURFACE BLOCK
        'surface_Carpet': [is_carpet], 
        'surface_Clay': [is_clay],
        'surface_Grass': [is_grass], 
        'surface_Hard': [is_hard]
    }
    
    df = pd.DataFrame(data)
    prob_p1 = model.predict_proba(df)[0][1]
    
    return prob_p1, ht_diff, fatigue_diff

def run_bot():
    print("--- STARTING DAILY TENNIS BOT ---")
    model, live_stats = load_system()
    db_names = list(live_stats.keys())
    
    web_matches = get_schedule()
    print(f"Found {len(web_matches)} matches online today.")
    
    predictions = []
    
    print("\nProcessing Matches...")
    for m in web_matches:
        # Match P1 Name
        p1_db, s1 = fuzzy_match_player(m['p1_web'], db_names)
        # Match P2 Name
        p2_db, s2 = fuzzy_match_player(m['p2_web'], db_names)
        
        # Only predict if we are confident on BOTH names
        if p1_db and p2_db:
            try:
                prob, ht, fat = predict_match_god_mode(model, live_stats, p1_db, p2_db, m['surface'])
                
                # Fair Odds Calculation
                fair_odds_1 = 1 / prob
                fair_odds_2 = 1 / (1 - prob)
                
                # Console Output for high-confidence bets
                # (Optional: Only print if prob > 60% or < 40%)
                print(f"[{m['surface']}] {p1_db} ({prob:.1%}) vs {p2_db}")
                
                predictions.append({
                    'Date': datetime.date.today(),
                    'Player 1': p1_db,
                    'Fair Odds 1': round(fair_odds_1, 2),
                    'Player 2': p2_db,
                    'Fair Odds 2': round(fair_odds_2, 2),
                    'Surface': m['surface'],
                    'Win % P1': round(prob * 100, 1),
                    'Fatigue Diff': fat,
                    'Height Diff': ht,
                    'Model Conf': 'High' if abs(prob - 0.5) > 0.15 else 'Low'
                })
            except Exception as e:
                # print(f"Error predicting {p1_db} vs {p2_db}: {e}")
                pass
                
    if predictions:
        # Save to CSV
        df = pd.DataFrame(predictions)
        # Sort by Win % to see best bets at the top
        df = df.sort_values('Win % P1', ascending=False)
        df.to_csv(OUTPUT_CSV, index=False)
        print(f"\n[SUCCESS] Saved {len(predictions)} predictions to {OUTPUT_CSV}")
        print("Open the CSV to see your betting lines.")
    else:
        print("No valid matches found matching your database.")

if __name__ == "__main__":
    run_bot()