import pandas as pd
import xgboost as xgb
import json
import numpy as np

# --- CONFIGURATION ---
MODEL_FILE = "tennis_model_god_mode.json"
LIVE_STATS_FILE = "players_live.json"

def load_system():
    print("Loading God Mode System...")
    model = xgb.XGBClassifier()
    model.load_model(MODEL_FILE)
    
    with open(LIVE_STATS_FILE, 'r') as f:
        live_stats = json.load(f)
        
    return model, live_stats

def predict(p1_name, p2_name, surface, model, live_stats):
    if p1_name not in live_stats: 
        print(f"Error: {p1_name} not found.")
        return
    if p2_name not in live_stats: 
        print(f"Error: {p2_name} not found.")
        return
    
    p1 = live_stats[p1_name]
    p2 = live_stats[p2_name]
    
    # Calculate Diffs
    ht_diff = p1['height'] - p2['height']
    fatigue_diff = p1['fatigue'] - p2['fatigue']
    
    # Surface
    is_carpet = 1 if surface == 'Carpet' else 0
    is_clay = 1 if surface == 'Clay' else 0
    is_grass = 1 if surface == 'Grass' else 0
    is_hard = 1 if surface == 'Hard' else 0

    # --- DATA DICTIONARY (STRICT ORDER MATCHING TRAINING) ---
    data = {
        'p1_elo': [p1['elo']], 'p2_elo': [p2['elo']],
        'p1_form': [p1['form_20']], 'p2_form': [p2['form_20']],
        'p1_momentum': [p1['momentum_5']], 'p2_momentum': [p2['momentum_5']],
        'p1_serve': [p1['serve']], 'p2_serve': [p2['serve']],
        'p1_return': [p1['return']], 'p2_return': [p2['return']],
        'p1_exp': [np.log1p(p1['matches'])], 'p2_exp': [np.log1p(p2['matches'])],
        
        # GOD MODE BLOCK
        'p1_pressure': [p1['pressure']], 
        'p2_pressure': [p2['pressure']],
        'fatigue_diff': [fatigue_diff],
        'height_diff': [ht_diff],
        'p1_is_lefty': [p1['hand']],
        'p2_is_lefty': [p2['hand']],
        
        # SURFACE BLOCK
        'surface_Carpet': [is_carpet], 
        'surface_Clay': [is_clay],
        'surface_Grass': [is_grass], 
        'surface_Hard': [is_hard]
    }
    
    df = pd.DataFrame(data)
    
    # Predict
    prob_p1 = model.predict_proba(df)[0][1]
    
    print(f"\n--- {surface.upper()} PREDICTION ---")
    print(f"{p1_name} vs {p2_name}")
    print(f"-------------------------------------------")
    print(f"{p1_name}: {prob_p1:.1%} (Odds: {1/prob_p1:.2f})")
    print(f"{p2_name}: {1-prob_p1:.1%} (Odds: {1/(1-prob_p1):.2f})")
    print(f"-------------------------------------------")
    print(f"Factors: Fatigue Diff {fatigue_diff} | Height Diff {ht_diff}cm")
    print(f"Clutch: {p1['pressure']:.1%} vs {p2['pressure']:.1%}")

if __name__ == "__main__":
    model, live = load_system()
    
    while True:
        print("\nType player names (or 'q' to quit):")
        p1 = input("Player 1: ").strip()
        if p1 == 'q': break
        p2 = input("Player 2: ").strip()
        if not p2: break
        surf = input("Surface: ").strip()
        
        try:
            predict(p1, p2, surf, model, live)
        except Exception as e:
            print(f"Error: {e}")