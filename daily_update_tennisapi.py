import requests
import sqlite3
import json
from datetime import datetime, timedelta

# --- CONFIGURATION ---
API_KEY = "39c716c052mshef8a7bf43953ef6p11b284jsnf4d9e5df15ee"
API_HOST = "tennisapi1.p.rapidapi.com"
BASE_URL = f"https://{API_HOST}/api/tennis"
DB_FILE = "tennis_data.db"

def get_headers():
    return {
        "X-RapidAPI-Key": API_KEY,
        "X-RapidAPI-Host": API_HOST
    }

def format_score(event):
    """
    Extracts set-by-set score instead of just '2-0'.
    Returns string like '6-4 6-3'
    """
    try:
        # TennisAPI usually provides scores in the 'homeScore'/'awayScore' blocks 
        # specifically under 'period1', 'period2', etc.
        home_score = event.get('homeScore', {})
        away_score = event.get('awayScore', {})
        
        scores = []
        # Check up to 5 sets
        for i in range(1, 6):
            p_key = f'period{i}'
            h_set = home_score.get(p_key)
            a_set = away_score.get(p_key)
            
            # Use 'display' or raw value. Sometimes it's None or 0 if set didn't happen.
            if h_set is not None and a_set is not None:
                # Some API responses use a specific 'display' field inside the period
                # Others just give the number.
                if isinstance(h_set, dict): h_val = h_set.get('display')
                else: h_val = h_set
                
                if isinstance(a_set, dict): a_val = a_set.get('display')
                else: a_val = a_set
                
                if h_val is not None and a_val is not None:
                    scores.append(f"{h_val}-{a_val}")
        
        if not scores:
            # Fallback to the display score if individual sets fail
            return f"{home_score.get('display',0)}-{away_score.get('display',0)}"
            
        return " ".join(scores)
    except:
        return "N/A"

def update_daily():
    print("--- STARTING DAILY UPDATE (TENNIS API) ---")
    
    # 1. Get Yesterday's Date
    date_obj = datetime.now() - timedelta(days=1)
    date_str = date_obj.strftime("%d/%m/%Y")
    
    # Store date in SQL format YYYY-MM-DD for consistency
    sql_date = date_obj.strftime("%Y-%m-%d")
    
    print(f"Fetching matches for {date_str}...")
    
    url = f"{BASE_URL}/events/{date_str}"
    
    try:
        response = requests.get(url, headers=get_headers())
        data = response.json()
        events = data.get('events', [])
    except Exception as e:
        print(f"API Error: {e}")
        return

    print(f"Found {len(events)} matches.")
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    matches_added = 0
    skipped_duplicates = 0
    
    for event in events:
        # Only process FINISHED matches
        if event.get('status', {}).get('type') != 'finished':
            continue
            
        try:
            # Basic Info
            tourney = event.get('tournament', {}).get('name', 'Unknown')
            p1_name = event['homeTeam']['name']
            p2_name = event['awayTeam']['name']
            winner_code = event.get('winnerCode') # 1 (Home) or 2 (Away)
            
            if not winner_code: continue
            
            # Determine Winner/Loser
            if winner_code == 1:
                w_name, l_name = p1_name, p2_name
            else:
                w_name, l_name = p2_name, p1_name
            
            # Better Score Parsing
            score_str = format_score(event)

            # Surface Logic
            raw_surface = event.get('tournament', {}).get('surface', 'Hard')
            if 'Clay' in raw_surface: surface = 'Clay'
            elif 'Grass' in raw_surface: surface = 'Grass'
            elif 'Carpet' in raw_surface: surface = 'Carpet'
            else: surface = 'Hard'
            
            # --- DEEP DUPLICATE CHECK ---
            # Instead of relying on INSERT OR IGNORE, we check explicitly.
            check_query = """
                SELECT 1 FROM matches 
                WHERE tourney_date = ? AND winner_name = ? AND loser_name = ?
            """
            cursor.execute(check_query, (sql_date, w_name, l_name))
            exists = cursor.fetchone()
            
            if exists:
                skipped_duplicates += 1
                continue

            # 4. INSERT INTO DATABASE
            cursor.execute("""
                INSERT INTO matches 
                (tourney_date, winner_name, loser_name, score, surface) 
                VALUES (?, ?, ?, ?, ?)
            """, (sql_date, w_name, l_name, score_str, surface))
            
            matches_added += 1
            if matches_added % 10 == 0: print(f"   Processed {matches_added} matches...")
            
        except Exception as e:
            continue

    conn.commit()
    conn.close()
    
    print(f"DONE: Added {matches_added} matches. Skipped {skipped_duplicates} duplicates.")
    
    # 5. TRIGGER LIVE STATE UPDATE
    print("Updating Player Ratings...")
    try:
        import save_current_state_v4 
        save_current_state_v4.save_state()
    except ImportError:
        print("Warning: save_current_state_v4.py not found. Player ratings not updated.")

if __name__ == "__main__":
    update_daily()