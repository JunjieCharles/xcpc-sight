import argparse
import csv
import json
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
import math
import random
from collections import defaultdict, Counter

from .paths import MODEL_FILE, PROCESSED_DATA_DIR, ensure_directory

def read_data(filename):
    data = []
    with open(filename, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data

def get_filtered_data(data, min_rating=1200, balance_difficulties=False):
    X_list = [] # [rating, difficulty]
    y_list = [] # time
    
    ratings = []
    difficulties = []
    times = []

    for row in data:
        try:
            r = int(row['userRating'])
            d = int(row['problemRating'])
            t_sec = float(row['timeConsumed'])
            contest_duration = float(row['contestDurationSeconds'])
            t = t_sec # Use seconds for training
            
            # Keep only times within the duration of their own contest.
            if r >= min_rating and 0 < t <= contest_duration:
                ratings.append(r)
                difficulties.append(d)
                times.append(t)
        except (KeyError, ValueError):
            continue
            
    if not ratings:
        return [], []

    # Outlier removal (Global IQR on log-time)
    # Since we expect log-normal distribution of times
    log_times = np.log(np.array(times))
    
    q1 = np.percentile(log_times, 25)
    q3 = np.percentile(log_times, 75)
    iqr = q3 - q1
    upper = q3 + 1.5 * iqr
    lower = q1 - 1.5 * iqr
    
    mask = (log_times >= lower) & (log_times <= upper)
    
    ratings = np.array(ratings)[mask]
    difficulties = np.array(difficulties)[mask]
    times = np.array(times)[mask]
    
    if balance_difficulties:
        # Downsample frequent difficulty levels to reduce their influence.
        print("Balancing dataset...")
        bins = defaultdict(list)
        for index, difficulty in enumerate(difficulties):
            bins[difficulty].append(index)

        counts = [len(indices) for indices in bins.values()]
        if counts:
            print(f"  Initial samples: {len(ratings)}")
            print(f"  Difficulty levels: {len(bins)}")
            print(f"  Min samples/level: {min(counts)}")
            print(f"  Max samples/level: {max(counts)}")

            cap = max(int(np.median(counts)), 100)
            print(f"  Cap per difficulty level: {cap}")

            balanced_indices = []
            for indices in bins.values():
                if len(indices) > cap:
                    balanced_indices.extend(random.sample(indices, cap))
                else:
                    balanced_indices.extend(indices)

            random.shuffle(balanced_indices)
            ratings = ratings[balanced_indices]
            difficulties = difficulties[balanced_indices]
            times = times[balanced_indices]
            print(f"  Balanced samples: {len(ratings)}")
    
    for r, d, t in zip(ratings, difficulties, times):
        X_list.append([r, d])
        y_list.append(t)
        
    return X_list, y_list

def main():
    parser = argparse.ArgumentParser(description="Train the problem difficulty model.")
    parser.add_argument(
        "--balance-difficulties",
        action="store_true",
        help="Downsample frequent problem-rating levels before training.",
    )
    args = parser.parse_args()

    csv_file = PROCESSED_DATA_DIR / "training_data.csv"
    print(f"Reading {csv_file}...")
    data = read_data(csv_file)
    
    print("Filtering data...")
    all_X, all_y = get_filtered_data(
        data,
        min_rating=1600,
        balance_difficulties=args.balance_difficulties,
    )
    
    all_X = np.array(all_X)
    all_y = np.array(all_y)
    
    print(f"Total samples used: {len(all_X)}")
    
    if len(all_X) == 0:
        print("No data found.")
        return

    # Model 1: ln(T) = b0 + b1 * R + b2 * D
    # Features: R, D
    X_model1 = all_X
    y_log = np.log(all_y)
    
    reg1 = LinearRegression()
    reg1.fit(X_model1, y_log)
    y_pred1 = reg1.predict(X_model1)
    r2_1 = r2_score(y_log, y_pred1)
    
    b0 = reg1.intercept_
    b1, b2 = reg1.coef_

    ensure_directory(MODEL_FILE.parent)
    with open(MODEL_FILE, "w", encoding="utf-8") as model_file:
        json.dump(
            {
                "intercept": float(b0),
                "rating_coefficient": float(b1),
                "difficulty_coefficient": float(b2),
            },
            model_file,
            indent=2,
        )
    
    print("\n--- Model 1: ln(T) = b0 + b1 * R + b2 * D ---")
    print(f"R2 Score: {r2_1:.4f}")
    print(f"Intercept (b0): {b0:.4f}")
    print(f"Coeff R (b1):   {b1:.6f}")
    print(f"Coeff D (b2):   {b2:.6f}")
    print(f"Formula: T = {math.exp(b0):.4f} * e^({b1:.6f} * R + {b2:.6f} * D)")
    print(f"Saved model coefficients to {MODEL_FILE}")
    
    # Model 2: ln(T) = b0 + b1 * (D - R)
    # Features: (D - R)
    X_model2 = (all_X[:, 1] - all_X[:, 0]).reshape(-1, 1)
    
    reg2 = LinearRegression()
    reg2.fit(X_model2, y_log)
    y_pred2 = reg2.predict(X_model2)
    r2_2 = r2_score(y_log, y_pred2)
    
    b0_2 = reg2.intercept_
    b1_2 = reg2.coef_[0]
    
    print("\n--- Model 2: ln(T) = b0 + b1 * (D - R) ---")
    print(f"R2 Score: {r2_2:.4f}")
    print(f"Intercept (b0): {b0_2:.4f}")
    print(f"Coeff (D-R):    {b1_2:.6f}")
    print(f"Formula: T = {math.exp(b0_2):.4f} * e^({b1_2:.6f} * (D - R))")
    
    # Comparison
    print("\n--- Analysis ---")
    if r2_1 > r2_2 + 0.02:
        print("Model 1 (Separate R and D) is significantly better.")
        print("This implies that Difficulty and User Rating scale differently.")
    else:
        print("Model 2 (Relative Difficulty) is comparable or better.")
        print("This implies that the difference (Difficulty - Rating) is the main driver.")
        
    # Example Calculations
    print("\n--- Expected Times (Model 1) ---")
    test_cases = [
        (1500, 1500), # Average user on appropriate problem
        (2000, 2000), # Strong user on hard problem
        (1500, 800),  # Average user on easy problem
        (3000, 800),  # Top user on easy problem
        (1500, 2000), # Average user on hard problem
    ]
    
    for r, d in test_cases:
        ln_t = b0 + b1 * r + b2 * d
        t = math.exp(ln_t)
        print(f"Rating {r} solving Difficulty {d}: {t:.1f} sec ({t/60:.1f} min)")

if __name__ == "__main__":
    main()
