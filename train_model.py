import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.metrics import accuracy_score, log_loss
from sklearn.model_selection import train_test_split

# --- CONFIGURATION ---
DATA_FILE = "tennis_brain_features.csv"
MODEL_FILE = "tennis_model.json"

def train_tennis_model():
    print("--- LOADING DATA ---")
    df = pd.read_csv(DATA_FILE)
    
    # 1. THE MIRROR FLIP (Creating "Loser" rows)
    print("Augmenting data (Creating Winner/Loser balance)...")
    
    # Create a copy where we swap P1 and P2 stats
    df_loser = df.copy()
    
    # Swap columns (p1_elo <-> p2_elo, etc.)
    # We find all columns starting with 'p1_' and swap them with 'p2_'
    p1_cols = [c for c in df.columns if c.startswith('p1_')]
    p2_cols = [c.replace('p1_', 'p2_') for c in p1_cols]
    
    # Rename map: p1->temp, p2->p1, temp->p2
    rename_dict = {}
    for p1, p2 in zip(p1_cols, p2_cols):
        rename_dict[p1] = p2
        rename_dict[p2] = p1
        
    df_loser = df_loser.rename(columns=rename_dict)
    
    # Set target to 0 (because P1 is now the loser in this copy)
    df_loser['target'] = 0
    
    # Combine them
    full_df = pd.concat([df, df_loser], ignore_index=True)
    
    # 2. PREPROCESSING
    print("Preprocessing...")
    
    # Convert date to datetime for sorting
    full_df['date'] = pd.to_datetime(full_df['date'])
    full_df = full_df.sort_values('date')
    
    # Drop non-numeric columns that the model can't read (Names, Date)
    # We keep 'surface' to encode it
    features = full_df.drop(columns=['date', 'p1_name', 'p2_name', 'target'])
    target = full_df['target']
    
    # One-Hot Encoding for Surface (Hard=1, Clay=0... etc)
    features = pd.get_dummies(features, columns=['surface'])
    
    # 3. SPLITTING TRAIN vs TEST (Time-based split)
    # We train on old data, test on recent data (simulate real betting)
    split_date = '2024-01-01'
    
    mask_train = full_df['date'] < split_date
    mask_test = full_df['date'] >= split_date
    
    X_train = features[mask_train]
    y_train = target[mask_train]
    X_test = features[mask_test]
    y_test = target[mask_test]
    
    print(f"Training on {len(X_train)} matches (Pre-2024)")
    print(f"Testing on  {len(X_test)} matches (2024-2025)")
    
    # 4. TRAIN XGBOOST
    print("\n--- TRAINING MODEL ---")
    model = xgb.XGBClassifier(
        n_estimators=1000,      # Number of "trees" in the forest
        learning_rate=0.05,     # Speed of learning (lower is slower but more accurate)
        max_depth=4,            # Complexity of each tree
        objective='binary:logistic', # Predicting Probability (0-1)
        eval_metric='logloss',
        early_stopping_rounds=50,
        n_jobs=-1               # Use all CPU cores
    )
    
    # We pass the test set as "eval_set" so the model stops training if it stops improving
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=100  # Print progress every 100 rounds
    )
    
    # 5. EVALUATION
    print("\n--- RESULTS ---")
    preds = model.predict(X_test)
    probs = model.predict_proba(X_test)[:, 1] # Probability of P1 winning
    
    acc = accuracy_score(y_test, preds)
    loss = log_loss(y_test, probs)
    
    print(f"Accuracy: {acc:.2%}")
    print(f"Log Loss: {loss:.4f} (Lower is better)")
    
    # 6. FEATURE IMPORTANCE (What does the model care about?)
    print("\n--- WHAT MATTERS MOST? (Feature Importance) ---")
    importance = pd.DataFrame({
        'Feature': X_train.columns,
        'Importance': model.feature_importances_
    }).sort_values('Importance', ascending=False)
    
    print(importance.head(10))
    
    # Save the model
    model.save_model(MODEL_FILE)
    print(f"\nModel saved to {MODEL_FILE}")

if __name__ == "__main__":
    train_tennis_model()