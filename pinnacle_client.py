import requests
import json
import pandas as pd

# --- CONFIGURATION ---
API_KEY = "39c716c052mshef8a7bf43953ef6p11b284jsnf4d9e5df15ee"
API_HOST = "pinaculo.p.rapidapi.com"
SPORT_ID = 33  # Tennis

headers = {
    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": API_HOST
}

def american_to_decimal(american_odds):
    """Converts American odds (-110, +150) to Decimal (1.91, 2.50)."""
    try:
        odds = float(american_odds)
        if odds > 0:
            return round(1 + (odds / 100), 2)
        else:
            return round(1 + (100 / abs(odds)), 2)
    except:
        return 0.0

def clean_pinnacle_name(name):
    """Removes Pinnacle's extra tags like '(Sets)'."""
    return name.replace("(Sets)", "").replace("(Game)", "").strip()

def get_live_odds():
    print("--- FETCHING LIVE PINNACLE ODDS ---")
    
    # 1. Get Matchups (Who is playing?)
    url_matchups = f"https://{API_HOST}/api/pinaculo/sports/{SPORT_ID}/matchups"
    matchups_map = {}
    
    try:
        resp = requests.get(url_matchups, headers=headers, params={"withSpecials": "false"})
        if resp.status_code != 200:
            print("Error fetching matchups")
            return {}
            
        raw_matchups = resp.json()
        # Handle if wrapped in a key
        if isinstance(raw_matchups, dict) and 'matchups' in raw_matchups:
            raw_matchups = raw_matchups['matchups']
            
        print(f"Found {len(raw_matchups)} raw matchups.")
        
        # Create a map: ID -> {P1, P2, League}
        for m in raw_matchups:
            if 'participants' not in m: continue
            
            # Pinnacle usually has participants[0] = Home, [1] = Away
            p1 = next((p['name'] for p in m['participants'] if p['alignment'] == 'home'), "Unknown")
            p2 = next((p['name'] for p in m['participants'] if p['alignment'] == 'away'), "Unknown")
            
            matchups_map[m['id']] = {
                'p1': clean_pinnacle_name(p1),
                'p2': clean_pinnacle_name(p2),
                'league': m.get('league', {}).get('name', 'Unknown'),
                'start': m.get('startTime', '')
            }
            
    except Exception as e:
        print(f"Matchup Error: {e}")
        return {}

    # 2. Get Markets (The Odds)
    # We fetch ALL straight markets in one go (most efficient)
    url_markets = f"https://{API_HOST}/api/pinaculo/sports/{SPORT_ID}/markets/straight"
    final_odds = []
    
    try:
        resp = requests.get(url_markets, headers=headers)
        markets = resp.json()
        
        # Handle if wrapped
        if isinstance(markets, dict) and 'markets' in markets:
            markets = markets['markets']
            
        print(f"Scanning {len(markets)} market lines for Moneyline...")
        
        for m in markets:
            # Filter for Pre-Match Moneyline (period 0)
            if m.get('type') == 'moneyline' and m.get('period') == 0:
                match_id = m.get('matchupId')
                
                if match_id in matchups_map:
                    match_info = matchups_map[match_id]
                    
                    # Extract Prices
                    # Usually a list of dicts: [{'designation': 'home', 'price': -150}, ...]
                    prices = m.get('prices', [])
                    home_price = next((x['price'] for x in prices if x['designation'] == 'home'), None)
                    away_price = next((x['price'] for x in prices if x['designation'] == 'away'), None)
                    
                    if home_price and away_price:
                        # Convert to Decimal
                        dec_1 = american_to_decimal(home_price)
                        dec_2 = american_to_decimal(away_price)
                        
                        final_odds.append({
                            'Player 1': match_info['p1'],
                            'Player 2': match_info['p2'],
                            'Odds 1': dec_1,
                            'Odds 2': dec_2,
                            'League': match_info['league']
                        })

    except Exception as e:
        print(f"Market Error: {e}")
        return {}
        
    # Convert to DataFrame for clean display
    if final_odds:
        df = pd.DataFrame(final_odds)
        print(f"\nSuccessfully extracted {len(df)} betting lines.")
        print(df.head())
        return df
    else:
        print("No Moneyline odds found.")
        return None

if __name__ == "__main__":
    get_live_odds()