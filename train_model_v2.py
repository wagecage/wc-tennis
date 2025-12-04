import pandas as pd
import xgboost as xgb
from sklearn.metrics import accuracy_score, log_loss

# --- CONFIGURATION ---
TRAIN_FILE = "tennis_brain_features.csv"
MODEL_FILE = "tennis_model_god_mode.json"

def train_final():
    print("--- TRAINING FINAL MODEL (NO LEAKAGE) ---")
    
    # 1. Load Data
    df = pd.read_csv(TRAIN_FILE)
    
    # 2. Augment Data (Mirror Flip)
    print("Augmenting data...")
    df_loser = df.copy()
    
    # Identify P1 columns automatically
    p1_cols = [c for c in df.columns if c.startswith('p1_')]
    p2_cols = [c.replace('p1_', 'p2_') for c in p1_cols]
    
    # Swap columns
    rename_dict = {}
    for p1, p2 in zip(p1_cols, p2_cols):
        rename_dict[p1] = p2
        rename_dict[p2] = p1
        
    df_loser = df_loser.rename(columns=rename_dict)
    
    # Flip the Target and the Diff stats
    df_loser['target'] = 0
    df_loser['fatigue_diff'] = -df_loser['fatigue_diff'] 
    df_loser['height_diff'] = -df_loser['height_diff']
    
    # Combine
    full_df = pd.concat([df, df_loser], ignore_index=True)
    full_df['date'] = pd.to_datetime(full_df['date'])
    full_df = full_df.sort_values('date')
    
    # 3. Prepare for Training
    # FIX: We only drop 'date' and 'target'. 
    # (p1_name and p2_name are essentially already gone, so we don't try to drop them)
    features = full_df.drop(columns=['date', 'target'])
    target = full_df['target']
    
    # One-Hot Encode Surface
    features = pd.get_dummies(features, columns=['surface'])
    
    # 4. Split
    split_date = '2024-01-01'
    mask_train = full_df['date'] < split_date
    mask_test = full_df['date'] >= split_date
    
    X_train = features[mask_train]
    y_train = target[mask_train]
    X_test = features[mask_test]
    y_test = target[mask_test]
    
    print(f"Training on {len(X_train)} rows...")
    
    # 5. Train
    model = xgb.XGBClassifier(
        n_estimators=1000,
        learning_rate=0.05,
        max_depth=4,
        objective='binary:logistic',
        early_stopping_rounds=50,
        n_jobs=-1
    )
    
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=100
    )
    
    # 6. Evaluate
    preds = model.predict(X_test)
    acc = accuracy_score(y_test, preds)
    print(f"\nREALISTIC ACCURACY: {acc:.2%}")
    
    model.save_model(MODEL_FILE)
    print(f"Model saved to {MODEL_FILE}")

if __name__ == "__main__":
    train_final()