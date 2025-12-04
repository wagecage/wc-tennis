import pandas as pd
import xgboost as xgb
import json
import numpy as np

# --- CONFIGURATION ---
MODEL_FILE = "tennis_model.json"
STATS_FILE = "players_live.json"

def load_system():
    print("Loading Brain (Model) and Memory (Stats)...")
    
    # Load Model
    model = xgb.XGBClassifier()
    model.load_model(MODEL_FILE)
    
    # Load Stats
    with open(STATS_FILE, 'r') as f:
        players = json.load(f)
        
    return model, players

def predict(p1_name, p2_name, surface, model, players):
    # Check if players exist
    if p1_name not in players:
        return f"Error: {p1_name} not found in database."
    if p2_name not in players:
        return f"Error: {p2_name} not found in database."
        
    p1 = players[p1_name]
    p2 = players[p2_name]
    
    # 1. Map surface string to columns
    # We must match the EXACT columns the model saw during training.
    # Training data had: surface_Carpet, surface_Clay, surface_Grass, surface_Hard
    is_carpet = 1 if surface == 'Carpet' else 0
    is_clay = 1 if surface == 'Clay' else 0
    is_grass = 1 if surface == 'Grass' else 0
    is_hard = 1 if surface == 'Hard' else 0
    
    # 2. Get Surface Win % for the specific surface requested
    p1_surf_key = f"surface_{surface.lower()}"
    p2_surf_key = f"surface_{surface.lower()}"
    
    p1_surf_val = p1.get(p1_surf_key, 0.5)
    p2_surf_val = p2.get(p2_surf_key, 0.5)

    # 3. Create DataFrame
    data = {
        'p1_elo': [p1['elo']],
        'p2_elo': [p2['elo']],
        'p1_form': [p1['form_20']],
        'p2_form': [p2['form_20']],
        'p1_momentum': [p1['momentum_5']],
        'p2_momentum': [p2['momentum_5']],
        'p1_serve': [p1['serve']],
        'p2_serve': [p2['serve']],
        'p1_return': [p1['return']],
        'p2_return': [p2['return']],
        'p1_comeback': [p1['comeback']],
        'p2_comeback': [p2['comeback']],
        'p1_exp': [np.log1p(p1['matches'])],
        'p2_exp': [np.log1p(p2['matches'])],
        
        # SURFACE COLUMNS (Must be in alphabetical order usually)
        'surface_Carpet': [is_carpet],  # This was the missing key!
        'surface_Clay': [is_clay],
        'surface_Grass': [is_grass],
        'surface_Hard': [is_hard]
    }
    
    df = pd.DataFrame(data)
    
    # Predict
    prob_p1 = model.predict_proba(df)[0][1]
    prob_p2 = 1 - prob_p1
    
    # Calculate Fair Odds
    odds_p1 = 1 / prob_p1
    odds_p2 = 1 / prob_p2
    
    print(f"\n--- PREDICTION: {surface.upper()} COURT ---")
    print(f"{p1_name} vs {p2_name}")
    print(f"-------------------------------------------")
    print(f"{p1_name}: {prob_p1:.1%}  (Fair Odds: {odds_p1:.2f})")
    print(f"{p2_name}: {prob_p2:.1%}  (Fair Odds: {odds_p2:.2f})")
    print(f"-------------------------------------------")
    
    # Stats Comparison
    print(f"Elo: {p1['elo']} vs {p2['elo']}")
    print(f"Form: {p1['form_20']:.2f} vs {p2['form_20']:.2f}")
    print(f"Surface Skill: {p1_surf_val:.2f} vs {p2_surf_val:.2f}")

# --- MAIN LOOP ---
if __name__ == "__main__":
    model, players = load_system()
    
    while True:
        print("\nType player names exactly as they appear in the database.")
        print("Example: Novak Djokovic")
        p1 = input("Player 1: ").strip()
        p2 = input("Player 2: ").strip()
        surf = input("Surface (Hard/Clay/Grass): ").strip()
        
        if not p1 or not p2: break
        
        try:
            predict(p1, p2, surf, model, players)
        except Exception as e:
            print(f"Error: {e}")