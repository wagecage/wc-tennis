import time
import pandas as pd
import json
import requests
import datetime
import os
import xgboost as xgb
import numpy as np
from rapidfuzz import process, fuzz
from sqlalchemy import create_engine, text

# Import Helpers
import pinnacle_client
import tennis_config

# --- CONFIGURATION ---
POLL_INTERVAL = 600  # 10 Minutes
MIN_EV_THRESHOLD = 0.05  # 5% EV

# --- SETUP & LOGGING ---
def log(msg):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

# Initialize Database Connection Engine (Cloud)
engine = create_engine(tennis_config.DB_URL)

def init_db():
    # PostgreSQL syntax: SERIAL is used for auto-incrementing IDs
    # We add a check to ensure the table exists with the correct columns
    create_table_sql = """
        CREATE TABLE IF NOT EXISTS bets (
            id SERIAL PRIMARY KEY,
            match_id INTEGER UNIQUE,
            date TEXT,
            start_time INTEGER,
            tournament TEXT,
            surface TEXT,
            player_1 TEXT,
            player_2 TEXT,
            bet_on TEXT,
            odds REAL,
            model_prob REAL,
            stake REAL DEFAULT 1.0,
            result TEXT,
            profit REAL,
            status TEXT DEFAULT 'Tracking',
            last_update TEXT
        );
    """
    try:
        with engine.connect() as conn:
            conn.execute(text(create_table_sql))
            conn.commit()
    except Exception as e:
        log(f"DB Init Error: {e}")

def repair_db():
    """Drops the bets table so it can be recreated with the correct schema."""
    log("⚠️ ATTEMPTING DB REPAIR: Dropping 'bets' table to fix schema mismatch...")
    try:
        with engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS bets;"))
            conn.commit()
        log("✅ Table dropped. Re-initializing...")
        init_db()
        log("✅ Database repaired. New schema applied.")
    except Exception as e:
        log(f"❌ Repair failed: {e}")

# --- LOAD RESOURCES ---
def load_resources():
    log("Loading resources (Players, Model)...")
    if not os.path.exists("players_live.json"): 
        log("ERROR: players_live.json not found.")
        return None, None, None
    
    with open("players_live.json", "r") as f: players = json.load(f)
    
    pressure = {}
    if os.path.exists("player_pressure_stats.json"):
        with open("player_pressure_stats.json", "r") as f: pressure = json.load(f)
            
    model = xgb.XGBClassifier()
    if os.path.exists("tennis_model_god_mode.json"): 
        model.load_model("tennis_model_god_mode.json")
    else: 
        model = None
        
    return players, pressure, model

# --- CORE LOGIC ---
def fetch_schedule_with_status():
    date_str = datetime.date.today().strftime("%d/%m/%Y")
    # Use config for Host/Key
    url = f"https://{tennis_config.TENNIS_API_HOST}/api/tennis/events/{date_str}"
    headers = {
        "X-RapidAPI-Key": tennis_config.TENNIS_API_KEY, 
        "X-RapidAPI-Host": tennis_config.TENNIS_API_HOST
    }
    
    matches = []
    try:
        response = requests.get(url, headers=headers)
        events = response.json().get('events', [])
        
        for e in events:
            # Basic Filter
            p1 = e['homeTeam']['name']
            p2 = e['awayTeam']['name']
            if '/' in p1 or '/' in p2: continue # No Doubles

            # Robust Surface Detection
            check_str = str(e).lower()
            if 'clay' in check_str: surf = 'Clay'
            elif 'grass' in check_str: surf = 'Grass'
            elif 'carpet' in check_str: surf = 'Carpet'
            else: surf = 'Hard'

            matches.append({
                'id': e['id'],
                'startTimestamp': e['startTimestamp'],
                'status': e.get('status', {}).get('type'), # finished, notstarted, inprogress
                'winnerCode': e.get('winnerCode'),
                'p1': p1,
                'p2': p2,
                'tourney': e.get('tournament', {}).get('name'),
                'surface': surf
            })
    except Exception as e:
        log(f"API Error: {e}")
    
    return matches

def run_prediction(players, pressure_stats, model, db_names, p1_name, p2_name, surface):
    p1_match = process.extractOne(p1_name, db_names, scorer=fuzz.token_set_ratio)
    p2_match = process.extractOne(p2_name, db_names, scorer=fuzz.token_set_ratio)
    
    if not p1_match or not p2_match: return None, None, 0.5
    
    p1_db, p2_db = p1_match[0], p2_match[0]
    p1, p2 = players[p1_db], players[p2_db]
    
    # Features
    ht_diff = p1.get('height', 185) - p2.get('height', 185)
    fatigue_diff = p1.get('fatigue', 0) - p2.get('fatigue', 0)
    p1_clutch = pressure_stats.get(p1_db, p1.get('pressure', 0.60))
    p2_clutch = pressure_stats.get(p2_db, p2.get('pressure', 0.60))
    
    is_hard = 1 if surface == 'Hard' else 0
    is_clay = 1 if surface == 'Clay' else 0
    is_grass = 1 if surface == 'Grass' else 0
    is_carpet = 1 if surface == 'Carpet' else 0

    input_data = {
        'p1_elo': [p1['elo']], 'p2_elo': [p2['elo']],
        'p1_form': [p1['form_20']], 'p2_form': [p2['form_20']],
        'p1_momentum': [p1['momentum_5']], 'p2_momentum': [p2['momentum_5']],
        'p1_serve': [p1['serve']], 'p2_serve': [p2['serve']],
        'p1_return': [p1['return']], 'p2_return': [p2['return']],
        'p1_exp': [np.log1p(p1['matches'])], 'p2_exp': [np.log1p(p2['matches'])],
        'p1_pressure': [p1_clutch], 'p2_pressure': [p2_clutch],
        'fatigue_diff': [fatigue_diff], 'height_diff': [ht_diff],
        'p1_is_lefty': [p1.get('hand', 0)], 'p2_is_lefty': [p2.get('hand', 0)],
        'surface_Carpet': [is_carpet], 'surface_Clay': [is_clay], 
        'surface_Grass': [is_grass], 'surface_Hard': [is_hard]
    }
    
    df = pd.DataFrame(input_data)
    prob = model.predict_proba(df)[0][1]
    return p1_db, p2_db, prob

def get_match_odds(p1, p2, odds_df):
    if odds_df is None or odds_df.empty: return None, None
    match1 = process.extractOne(p1, odds_df['Player 1'], scorer=fuzz.token_set_ratio)
    if not match1 or match1[1] < 85: return None, None
    row_idx = match1[2]
    odds_p2 = odds_df.iloc[row_idx]['Player 2']
    if fuzz.token_set_ratio(p2, odds_p2) > 85:
        return odds_df.iloc[row_idx]['Odds 1'], odds_df.iloc[row_idx]['Odds 2']
    return None, None

# --- MAIN LOOP ---
def main_loop():
    init_db()
    players, pressure, model = load_resources()
    if not players: return

    db_names = list(players.keys())

    # --- AUTO REPAIR CHECK ---
    # We check if the table is readable. If not, we repair it.
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT match_id FROM bets LIMIT 1"))
    except Exception as e:
        if "UndefinedColumn" in str(e) or "does not exist" in str(e):
            repair_db()

    while True:
        log("--- Starting Scan Cycle ---")
        
        # 1. Fetch Data
        api_matches = fetch_schedule_with_status()
        log(f"Fetched {len(api_matches)} matches from API.")
        
        # Call the new Pinnacle Client file
        odds_df = pinnacle_client.get_live_odds()
        log(f"Fetched Live Odds ({len(odds_df)} markets).")

        current_time = int(time.time())

        # Establish DB Connection for this cycle
        # We use a context manager to ensure the connection is closed after each cycle
        with engine.connect() as conn:
            
            for m in api_matches:
                p1_db, p2_db, prob = run_prediction(players, pressure, model, db_names, m['p1'], m['p2'], m['surface'])
                if not p1_db: continue

                o1, o2 = get_match_odds(p1_db, p2_db, odds_df)
                
                ev1 = (prob * o1) - 1 if o1 else -1
                ev2 = ((1-prob) * o2) - 1 if o2 else -1

                target_p, target_o, target_ev = None, 0, 0
                if ev1 > MIN_EV_THRESHOLD:
                    target_p, target_o, target_ev = p1_db, o1, ev1
                elif ev2 > MIN_EV_THRESHOLD:
                    target_p, target_o, target_ev = p2_db, o2, ev2
                
                # --- TYPE CASTING (CRITICAL FOR POSTGRES) ---
                # Numpy types cause errors in SQL Alchemy/Postgres
                if target_o: target_o = float(target_o)
                prob = float(prob)
                match_id = int(m['id'])
                start_ts = int(m['startTimestamp'])
                # --------------------------------------------

                # Check Existing Bet using PostgreSQL Parameter syntax (:param)
                result = conn.execute(text("SELECT id, status, odds FROM bets WHERE match_id = :mid"), {"mid": match_id}).fetchone()
                
                # A: NEW BET
                if not result and target_p:
                    if m['status'] == 'notstarted':
                        log(f"FOUND BET: {target_p} @ {target_o} (EV: {target_ev:.1%})")
                        conn.execute(text("""
                            INSERT INTO bets (match_id, date, start_time, tournament, surface, player_1, player_2, bet_on, odds, model_prob, status, last_update)
                            VALUES (:mid, :date, :stime, :tourn, :surf, :p1, :p2, :bet_on, :odds, :prob, 'Tracking', :upd)
                        """), {
                            "mid": match_id, "date": datetime.date.today(), "stime": start_ts,
                            "tourn": m['tourney'], "surf": m['surface'], "p1": p1_db, "p2": p2_db,
                            "bet_on": target_p, "odds": target_o, "prob": prob, "upd": str(datetime.datetime.now())
                        })
                        conn.commit()

                # B: UPDATE TRACKING (Odds Change)
                elif result and result[1] == 'Tracking':
                    bet_id = result[0]
                    # Lock if started
                    if current_time >= start_ts or m['status'] != 'notstarted':
                        log(f"LOCKING BET: ID {bet_id} (Match Started)")
                        conn.execute(text("UPDATE bets SET status = 'Pending' WHERE id = :bid"), {"bid": bet_id})
                        conn.commit()
                    # Update Odds
                    elif target_p and target_o != result[2]:
                        # Update odds to reflect live movement
                        conn.execute(text("UPDATE bets SET odds = :odds, last_update = :upd WHERE id = :bid"), 
                                     {"odds": target_o, "upd": str(datetime.datetime.now()), "bid": bet_id})
                        conn.commit()

                # C: RESOLVE FINISHED BETS
                elif result and result[1] == 'Pending':
                    bet_id = result[0]
                    if m['status'] == 'finished' and m['winnerCode']:
                        # Determine winner
                        winner_name = p1_db if m['winnerCode'] == 1 else p2_db
                        
                        # Fetch original bet details to calc profit
                        b_data = conn.execute(text("SELECT bet_on, odds, stake FROM bets WHERE id = :bid"), {"bid": bet_id}).fetchone()
                        pick, locked_odds, stake = b_data
                        
                        if pick == winner_name:
                            profit = (stake * locked_odds) - stake
                            res = "WIN"
                        else:
                            profit = -stake
                            res = "LOSS"
                        
                        log(f"RESOLVED BET {bet_id}: {res} ({profit:.2f})")
                        conn.execute(text("UPDATE bets SET result = :res, profit = :prof, status = 'Resolved' WHERE id = :bid"), 
                                     {"res": res, "prof": profit, "bid": bet_id})
                        conn.commit()

        log(f"Cycle Complete. Sleeping for {POLL_INTERVAL}s...")
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main_loop()