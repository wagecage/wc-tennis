import pandas as pd
import requests
import os
from io import StringIO

# --- CONFIGURATION ---
START_YEAR = 2000
END_YEAR = 2025
BASE_URL = "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master"

# Create a folder specifically for this data
OUTPUT_FOLDER = "data/raw"  # Best practice: keep data in a subfolder
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# List to hold all dataframes
all_matches = []

print(f"--- STARTING DOWNLOAD ({START_YEAR}-{END_YEAR}) ---")
print("Target: ATP Main Tour & Challengers Only (No ITF/Futures)")

for year in range(START_YEAR, END_YEAR + 1):
    print(f"\nProcessing {year}...")
    
    # We strictly select only these two file types per year
    files_to_download = [
        f"atp_matches_{year}.csv",             # Main Tour (Grand Slams, Masters, ATP 250/500)
        f"atp_matches_qual_chall_{year}.csv",  # Challengers & Qualifiers
    ]
    
    for filename in files_to_download:
        url = f"{BASE_URL}/{filename}"
        
        try:
            print(f"   Requesting {filename}...", end=" ")
            response = requests.get(url)
            
            if response.status_code == 404:
                print(f"[MISSING] File not found (normal for current year if not started yet)")
                continue
                
            response.raise_for_status()
            
            # Read CSV
            df = pd.read_csv(StringIO(response.text))
            
            # Add source column for traceability
            df['source_file'] = filename
            
            # Save individual backup
            local_path = os.path.join(OUTPUT_FOLDER, filename)
            df.to_csv(local_path, index=False)
            
            # Append to master list
            all_matches.append(df)
            print(f"[SUCCESS] - {len(df)} matches")
            
        except Exception as e:
            print(f"\n   [ERROR] Failed to download {filename}: {e}")

# --- COMBINE AND SAVE ---
if all_matches:
    print("\n--- COMBINING DATA ---")
    master_df = pd.concat(all_matches, ignore_index=True)
    
    # Save the cleaned master file in the main folder
    master_path = "atp_challengers_2000_2025.csv"
    master_df.to_csv(master_path, index=False)
    
    print(f"SUCCESS! Master file created: {master_path}")
    print(f"Total Matches Collected: {len(master_df)}")
    
    # Quick sanity check for you
    print("\n--- DATA PREVIEW ---")
    print(master_df[['tourney_name', 'winner_name', 'loser_name', 'score', 'surface']].head(3))
else:
    print("\nNo data downloaded.")