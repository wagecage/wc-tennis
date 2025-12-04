from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from pydantic import BaseModel
from typing import List, Optional, Dict
import datetime
import json
import os
import tennis_config

# --- CONFIGURATION ---
app = FastAPI(title="Tennis Brain API", version="1.0.0")

# --- CORS MIDDLEWARE ---
app.add_middleware(
    CORSMiddleware,
    # Allow both localhost (for testing) and your Vercel domain
    allow_origins=[
        "http://localhost:3000",
        "https://wc-tennis.vercel.app",
        "https://wc-tennis.vercel.app/", # Sometimes trailing slash matters
        "*" # Fallback
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Connect to Cloud DB
engine = create_engine(tennis_config.DB_URL)

# --- DATA MODELS (Response Schemas) ---
class Matchup(BaseModel):
    id: int
    date: str
    time: str
    tournament: str
    surface: str
    player_1: str
    player_2: str
    model_prob_p1: float
    model_prob_p2: float
    odds_p1: Optional[float]
    odds_p2: Optional[float]
    value_bet_on: Optional[str] 
    ev: float
    status: str

class BetResult(BaseModel):
    date: str
    tournament: str
    bet_on: str
    odds: float
    result: str 
    profit: float

class PlayerStats(BaseModel):
    name: str
    elo: int
    form: float
    clutch: float
    surface_hard: float
    surface_clay: float
    surface_grass: float

# --- ENDPOINTS ---

@app.get("/")
def health_check():
    return {"status": "online", "message": "Tennis Brain API is operational"}

@app.get("/players", response_model=List[PlayerStats])
def get_all_players():
    """
    Returns the full database of players from players_live.json
    """
    try:
        # Ensure file exists
        if not os.path.exists("players_live.json"):
            return []
            
        with open("players_live.json", "r") as f:
            data = json.load(f)
            
        players = []
        for name, stats in data.items():
            # Filter for active players with decent history (optional but cleaner)
            if stats.get('matches', 0) > 10:
                players.append({
                    "name": name,
                    "elo": int(stats.get('elo', 1500)),
                    "form": stats.get('form_20', 0.5),
                    "clutch": stats.get('pressure', 0.5),
                    "surface_hard": stats.get('surface_hard', 0.5),
                    "surface_clay": stats.get('surface_clay', 0.5),
                    "surface_grass": stats.get('surface_grass', 0.5)
                })
        
        # Sort by Elo descending
        return sorted(players, key=lambda x: x['elo'], reverse=True)
        
    except Exception as e:
        print(f"Error fetching players: {e}")
        # Raise HTTP exception so frontend catches it
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/matchups", response_model=List[Matchup])
def get_live_matchups():
    try:
        with engine.connect() as conn:
            # Query for live bets
            query = """
                SELECT id, start_time, tournament, surface, player_1, player_2, 
                       bet_on, odds, model_prob, status 
                FROM bets 
                WHERE status IN ('Tracking', 'Pending') 
                ORDER BY tournament, start_time ASC
            """
            result = conn.execute(text(query)).fetchall()
            
            matchups = []
            for row in result:
                dt = datetime.datetime.fromtimestamp(row.start_time)
                
                prob_p1 = row.model_prob
                prob_p2 = 1.0 - prob_p1
                
                # Logic for Odds Display
                odds_1 = row.odds if row.bet_on == row.player_1 else None
                odds_2 = row.odds if row.bet_on == row.player_2 else None
                
                # Logic for EV Display
                current_ev = 0.0
                if row.bet_on == row.player_1:
                    current_ev = (row.odds * prob_p1) - 1
                elif row.bet_on == row.player_2:
                    current_ev = (row.odds * prob_p2) - 1

                matchups.append({
                    "id": row.id,
                    "date": dt.strftime("%Y-%m-%d"),
                    "time": dt.strftime("%H:%M"),
                    "tournament": row.tournament,
                    "surface": row.surface,
                    "player_1": row.player_1,
                    "player_2": row.player_2,
                    "model_prob_p1": prob_p1,
                    "model_prob_p2": prob_p2,
                    "odds_p1": odds_1,
                    "odds_p2": odds_2,
                    "value_bet_on": row.bet_on,
                    "ev": round(current_ev, 3),
                    "status": row.status
                })
            return matchups
            
    except Exception as e:
        print(f"Error fetching matchups: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")

@app.get("/history", response_model=List[BetResult])
def get_betting_history():
    try:
        with engine.connect() as conn:
            query = """
                SELECT date, tournament, bet_on, odds, result, profit 
                FROM bets 
                WHERE status = 'Resolved' 
                ORDER BY date DESC 
                LIMIT 100
            """
            result = conn.execute(text(query)).fetchall()
            
            history = []
            for row in result:
                history.append({
                    "date": row.date,
                    "tournament": row.tournament,
                    "bet_on": row.bet_on,
                    "odds": row.odds,
                    "result": row.result,
                    "profit": row.profit
                })
            return history
            
    except Exception as e:
        print(f"Error fetching history: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")