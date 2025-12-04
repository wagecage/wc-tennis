import requests
import sqlite3
import time
from datetime import datetime, timedelta
import json

# --- CONFIGURATION ---
# We revert to the API that worked for you originally
API_KEY = "39c716c052mshef8a7bf43953ef6p11b284jsnf4d9e5df15ee"
API_HOST = "tennisapi1.p.rapidapi.com"
BASE_URL = f"https://{API_HOST}/api/tennis"
DB_FILE = "tennis_data.db"

# DATE RANGE
START_DATE = "2025-06-15"
END_DATE = datetime.now().strftime("%Y-%m-%d")

def get_headers():
    return {
        "X-RapidAPI-Key": API_KEY,
        "X-RapidAPI-Host": API_HOST
    }

def is_valid_match(event):
    """
    STRICT FILTER: Only Men's Singles (ATP/Challenger/ITF)
    Adapted for the TennisApi JSON structure
    """
    tourney = event.get('tournament', {}).get('name', '').lower()
    category = event.get('tournament', {}).get('category', {}).get('name', '').lower()
    full_name = f"{category} {tourney}"
    
    # 1. EXCLUDE (The "Banned" List)
    if 'women' in full_name or 'wta' in full_name: return False
    if 'doubles' in full_name: return False
    if 'mixed' in full_name: return False
    if 'junior' in full_name or 'boys' in full_name: return False
    
    # 2. INCLUDE (The "Allowed" List)
    # We explicitly look for Men's signals
    if 'atp' in full_name or 'challenger' in full_name or 'davis cup' in full_name:
        return True
    
    # ITF Handling: Accept ITF only if we are sure it's not Women's
    # (Since we already filtered 'women'/'wta' above, this helps, but we check 'men' to be safe)
    if 'itf' in full_name and ('men' in full_name or 'm15' in full_name or 'm25' in full_name):
        return True
        
    return False

def backfill_filtered():
    print(f"--- STARTING FILTERED BACKFILL ({START_DATE} to {END_DATE}) ---")
    
    start = datetime.strptime(START_DATE, "%Y-%m-%d")
    end = datetime.strptime(END_DATE, "%Y-%m-%d")
    current = start
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    total_matches = 0
    
    while current <= end:
        # FIX: TennisApi requires DD/MM/YYYY format
        date_str = current.strftime("%d/%m/%Y") 
        sql_date = current.strftime("%Y-%m-%d")
        
        print(f"Processing {date_str}...", end=" ")
        
        url = f"{BASE_URL}/events/{date_str}"
        
        try:
            response = requests.get(url, headers=get_headers())
            
            if response.status_code != 200:
                print(f"[API Error {response.status_code}]")
                current += timedelta(days=1)
                continue

            data = response.json()
            events = data.get('events', [])
            
            if not events:
                print("0 events found.")
                current += timedelta(days=1)
                continue
            
            day_matches = 0
            filtered_count = 0
            
            for event in events:
                # 1. APPLY FILTER
                if not is_valid_match(event): 
                    filtered_count += 1
                    continue
                
                # 2. Check Status
                status = event.get('status', {}).get('type')
                if status != 'finished':
                    continue
                
                # 3. Extract Info
                p1_name = event.get('homeTeam', {}).get('name', 'Unknown')
                p2_name = event.get('awayTeam', {}).get('name', 'Unknown')
                winner_code = event.get('winnerCode')
                
                if not winner_code: continue
                
                if winner_code == 1:
                    w_name, l_name = p1_name, p2_name
                else:
                    w_name, l_name = p2_name, p1_name
                
                score = event.get('homeScore', {}).get('display', '0-0')
                surface = "Hard" # TennisApi doesn't always provide surface in summary
                
                # Try to detect surface from tournament name
                t_name = event.get('tournament', {}).get('name', '').lower()
                if 'clay' in t_name: surface = 'Clay'
                elif 'grass' in t_name: surface = 'Grass'
                elif 'indoor' in t_name: surface = 'Hard'

                # 4. Insert
                cursor.execute("""
                    INSERT OR REPLACE INTO matches 
                    (tourney_date, winner_name, loser_name, score, surface) 
                    VALUES (?, ?, ?, ?, ?)
                """, (sql_date, w_name, l_name, score, surface))
                
                day_matches += 1
            
            print(f"Added {day_matches} matches. (Filtered out {filtered_count})")
            total_matches += day_matches
            conn.commit()
            
        except Exception as e:
            print(f"[Script Error] {e}")
        
        current += timedelta(days=1)
        # Sleep slightly to avoid rate limits
        time.sleep(0.2) 

    conn.close()
    print(f"\n[DONE] Filtered Backfill Complete. Added {total_matches} CLEAN matches.")
    
    # Update ratings immediately
    try:
        import save_current_state_v4
        save_current_state_v4.save_state()
    except ImportError:
        print("Could not auto-run save_current_state_v4. Please run it manually.")

if __name__ == "__main__":
    backfill_filtered()