import requests
import sqlite3
from datetime import datetime, timedelta
import time

# --- CONFIGURATION ---
API_KEY = "39c716c052mshef8a7bf43953ef6p11b284jsnf4d9e5df15ee"
API_HOST = "tennisapi1.p.rapidapi.com"
BASE_URL = f"https://{API_HOST}/api/tennis"
DB_FILE = "tennis_data.db"

# DATE RANGE TO BACKFILL
# Check your Jeff Sackmann CSVs to see the last date (e.g., 2024-11-01)
START_DATE = "2025-06-15" 
END_DATE = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

def get_headers():
    return {
        "X-RapidAPI-Key": API_KEY,
        "X-RapidAPI-Host": API_HOST
    }

def backfill_range():
    print(f"--- STARTING BACKFILL ({START_DATE} to {END_DATE}) ---")
    
    start = datetime.strptime(START_DATE, "%Y-%m-%d")
    end = datetime.strptime(END_DATE, "%Y-%m-%d")
    
    current = start
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    total_added = 0
    
    while current <= end:
        date_str = current.strftime("%d/%m/%Y") # API expects DD/MM/YYYY
        sql_date = current.strftime("%Y-%m-%d") # DB expects YYYY-MM-DD
        
        print(f"Processing {date_str}...", end=" ")
        
        url = f"{BASE_URL}/events/{date_str}"
        
        try:
            response = requests.get(url, headers=get_headers())
            data = response.json()
            events = data.get('events', [])
            
            day_count = 0
            for event in events:
                if event.get('status', {}).get('type') != 'finished':
                    continue
                
                # Basic Info Only (To save API calls)
                p1 = event['homeTeam']['name']
                p2 = event['awayTeam']['name']
                score = f"{event.get('homeScore',{}).get('display',0)}-{event.get('awayScore',{}).get('display',0)}"
                winner_code = event.get('winnerCode')
                
                if not winner_code: continue
                
                if winner_code == 1:
                    w, l = p1, p2
                else:
                    w, l = p2, p1
                
                # Insert into DB
                cursor.execute("""
                    INSERT OR IGNORE INTO matches 
                    (tourney_date, winner_name, loser_name, score, surface) 
                    VALUES (?, ?, ?, ?, ?)
                """, (sql_date, w, l, score, 'Hard')) # Default to Hard if unknown
                
                day_count += 1
            
            print(f"Added {day_count} matches.")
            total_added += day_count
            conn.commit()
            
        except Exception as e:
            print(f"Error: {e}")
        
        # Move to next day
        current += timedelta(days=1)
        # Sleep to be nice to the API
        time.sleep(1) 

    conn.close()
    print(f"\n[SUCCESS] Backfill Complete. Added {total_added} matches.")
    
    # UPDATE RATINGS
    print("Recalculating Player Ratings...")
    import save_current_state_v4
    save_current_state_v4.save_state()

if __name__ == "__main__":
    backfill_range()