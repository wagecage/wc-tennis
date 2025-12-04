import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
from rapidfuzz import process, fuzz
import predict_match  # Importing your previous script
import time

# --- CONFIGURATION ---
URL = "https://www.tennisexplorer.com/matches/"  # The target for daily matches
CONFIDENCE_THRESHOLD = 85  # Only bet if name match is > 85% sure

def get_page_content():
    """Fetches the HTML from TennisExplorer pretending to be a browser."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(URL, headers=headers)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching schedule: {e}")
        return None

def parse_schedule(html):
    """Extracts raw match strings from the HTML."""
    soup = BeautifulSoup(html, "html.parser")
    matches = []
    
    # TennisExplorer uses tables with class 'result'
    # We look for rows that contain match info
    tables = soup.find_all("table", class_="result")
    
    current_tournament = "Unknown"
    current_surface = "Hard" # Default fallback
    
    print("Parsing today's matches...")
    
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            # Detect Tournament Header (often has 't-name' class)
            if "head" in row.get("class", []):
                link = row.find("a")
                if link:
                    current_tournament = link.text.strip()
                    # simplistic surface detection from tournament name or you need a tournament DB
                    # For V1, we will default to Hard if unknown, or try to detect keywords
                    lower_name = current_tournament.lower()
                    if "clay" in lower_name: current_surface = "Clay"
                    elif "grass" in lower_name: current_surface = "Grass"
                    elif "hard" in lower_name: current_surface = "Hard"
                    elif "indoors" in lower_name: current_surface = "Hard"
            
            # Detect Match Row
            # Look for rows with player names
            p_cells = row.find_all("td", class_="t-name")
            if len(p_cells) >= 2:
                # Found a match!
                p1_raw = p_cells[0].find("a").text.strip()
                p2_raw = p_cells[1].find("a").text.strip()
                
                # Check for odds (to see if it's a valid betting match)
                matches.append({
                    "p1_web": p1_raw,
                    "p2_web": p2_raw,
                    "tournament": current_tournament,
                    "surface": current_surface
                })
                
    return matches

def match_names_to_db(web_matches, db_players):
    """
    The HARDEST part: Linking 'Sinner J.' (Web) to 'Jannik Sinner' (DB).
    """
    valid_matches = []
    db_names = list(db_players.keys())
    
    print(f"Fuzzy matching {len(web_matches)} matches against {len(db_names)} DB players...")
    
    for m in web_matches:
        # 1. Match Player 1
        # extractOne returns (match, score, index)
        p1_match = process.extractOne(m['p1_web'], db_names, scorer=fuzz.token_set_ratio)
        p2_match = process.extractOne(m['p2_web'], db_names, scorer=fuzz.token_set_ratio)
        
        if p1_match[1] > CONFIDENCE_THRESHOLD and p2_match[1] > CONFIDENCE_THRESHOLD:
            valid_matches.append({
                "p1_name": p1_match[0],
                "p2_name": p2_match[0],
                "surface": m['surface'],
                "orig_p1": m['p1_web'],
                "orig_p2": m['p2_web']
            })
        else:
            # print(f"Skipping ambiguous match: {m['p1_web']} vs {m['p2_web']}")
            pass
            
    return valid_matches

def run_daily_bot():
    # 1. Load the Brain
    model, players = predict_match.load_system()
    
    # 2. Get the Schedule
    html = get_page_content()
    if not html: return
    
    raw_matches = parse_schedule(html)
    print(f"Found {len(raw_matches)} raw matches on the schedule.")
    
    # 3. Normalize Names
    clean_matches = match_names_to_db(raw_matches, players)
    print(f"Successfully identified {len(clean_matches)} matches in your database.")
    
    # 4. Predict & Output
    print("\n" + "="*60)
    print(f"  DAILY PREDICTIONS FOR {datetime.date.today()}")
    print("="*60 + "\n")
    
    results = []
    
    for m in clean_matches:
        p1 = m['p1_name']
        p2 = m['p2_name']
        surf = m['surface']
        
        # We use a try/except block to catch any missing data issues
        try:
            # Reuse the logic from predict_match.py but we need to capture the output
            # So we will essentially copy the logic or import it. 
            # Ideally, refactor predict_match.py to return values, but for now we copy-paste the core logic here for speed.
            
            p1_stats = players[p1]
            p2_stats = players[p2]
            
            # Prepare Data Frame (Same as predict_match.py)
            is_carpet = 1 if surf == 'Carpet' else 0
            is_clay = 1 if surf == 'Clay' else 0
            is_grass = 1 if surf == 'Grass' else 0
            is_hard = 1 if surf == 'Hard' else 0
            
            p1_surf_val = p1_stats.get(f"surface_{surf.lower()}", 0.5)
            p2_surf_val = p2_stats.get(f"surface_{surf.lower()}", 0.5)

            import numpy as np
            data = {
                'p1_elo': [p1_stats['elo']], 'p2_elo': [p2_stats['elo']],
                'p1_form': [p1_stats['form_20']], 'p2_form': [p2_stats['form_20']],
                'p1_momentum': [p1_stats['momentum_5']], 'p2_momentum': [p2_stats['momentum_5']],
                'p1_serve': [p1_stats['serve']], 'p2_serve': [p2_stats['serve']],
                'p1_return': [p1_stats['return']], 'p2_return': [p2_stats['return']],
                'p1_comeback': [p1_stats['comeback']], 'p2_comeback': [p2_stats['comeback']],
                'p1_exp': [np.log1p(p1_stats['matches'])], 'p2_exp': [np.log1p(p2_stats['matches'])],
                'surface_Carpet': [is_carpet], 'surface_Clay': [is_clay],
                'surface_Grass': [is_grass], 'surface_Hard': [is_hard]
            }
            
            df = pd.DataFrame(data)
            prob_p1 = model.predict_proba(df)[0][1]
            
            # Print cleanly
            print(f"{p1} ({prob_p1:.1%}) vs {p2} ({1-prob_p1:.1%}) [{surf}]")
            
            results.append({
                'Player 1': p1, 'Prob 1': prob_p1,
                'Player 2': p2, 'Prob 2': 1-prob_p1,
                'Surface': surf,
                'Fair Odds 1': round(1/prob_p1, 2),
                'Fair Odds 2': round(1/(1-prob_p1), 2)
            })
            
        except Exception as e:
            # print(f"Error predicting {p1} vs {p2}: {e}")
            pass
            
    # 5. Save to CSV for you to bet
    if results:
        res_df = pd.DataFrame(results)
        filename = f"bets_{datetime.date.today()}.csv"
        res_df.to_csv(filename, index=False)
        print(f"\n[DONE] Saved {len(results)} predictions to {filename}")

if __name__ == "__main__":
    run_daily_bot()