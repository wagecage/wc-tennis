import os
from dotenv import load_dotenv

# Load .env file if it exists (for local development)
load_dotenv()

# --- WC TENNIS CONFIGURATION ---

# Database Connection
# It tries to get the value from the Environment (Render/.env), otherwise uses your local string
DB_URL = os.getenv("DB_URL", "postgresql://postgres.yftdoymvqsxkccwpoexd:TennisModel3112!@aws-1-ap-southeast-2.pooler.supabase.com:6543/postgres")

# TennisAPI
TENNIS_API_KEY = os.getenv("TENNIS_API_KEY", "39c716c052mshef8a7bf43953ef6p11b284jsnf4d9e5df15ee")
TENNIS_API_HOST = os.getenv("TENNIS_API_HOST", "tennisapi1.p.rapidapi.com")

# Pinnacle API
PINNACLE_API_KEY = os.getenv("PINNACLE_API_KEY", "39c716c052mshef8a7bf43953ef6p11b284jsnf4d9e5df15ee")
PINNACLE_API_HOST = os.getenv("PINNACLE_API_HOST", "pinaculo.p.rapidapi.com")