import csv
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
import math

from .paths import ANALYSIS_DIR

def read_data(filename):
    data = []
    with open(filename, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data, reader.fieldnames

def filter_data(data, problem_index, min_rating=1200):
    ratings = []
    times = []
    
    for row in data:
        try:
            r = int(row['rating'])
            t_str = row.get(problem_index)
            if not t_str:
                continue
            t = float(t_str) / 60.0 # Minutes
            
            if r >= min_rating and t > 0:
                ratings.append(r)
                times.append(t)
        except ValueError:
            continue
            
    return np.array(ratings), np.array(times)

def remove_outliers(ratings, times):
    if len(times) < 10:
        return ratings, times
        
    # Simple IQR filtering on Time
    q1 = np.percentile(times, 25)
    q3 = np.percentile(times, 75)
    iqr = q3 - q1
    upper_bound = q3 + 1.5 * iqr
    lower_bound = q1 - 1.5 * iqr
    
    mask = (times >= lower_bound) & (times <= upper_bound)
    return ratings[mask], times[mask]

def analyze_problem(problem_index, ratings, times):
    if len(ratings) < 20:
        print(f"Problem {problem_index}: Not enough data ({len(ratings)} samples)")
        return

    # 1. Linear Model: T = a * R + b
    X = ratings.reshape(-1, 1)
    y = times
    lin_reg = LinearRegression()
    lin_reg.fit(X, y)
    y_pred_lin = lin_reg.predict(X)
    r2_lin = r2_score(y, y_pred_lin)
    
    # 2. Log-Linear Model: ln(T) = a * R + b  => T = exp(b) * exp(a * R)
    # We fit Linear Regression on ln(T) vs R
    y_log = np.log(times)
    log_reg = LinearRegression()
    log_reg.fit(X, y_log)
    y_pred_log = log_reg.predict(X)
    r2_log = r2_score(y_log, y_pred_log)
    
    # Coefficients
    a_log = log_reg.coef_[0]
    b_log = log_reg.intercept_
    
    print(f"--- Problem {problem_index} ---")
    print(f"Samples: {len(ratings)}")
    print(f"Median Time: {np.median(times):.2f} min")
    print(f"Linear R2: {r2_lin:.4f}")
    print(f"Log-Linear R2: {r2_log:.4f}")
    print(f"Log-Linear Params: ln(T) = {a_log:.6f} * R + {b_log:.4f}")
    print(f"                   T = {math.exp(b_log):.2f} * e^({a_log:.6f} * R)")
    
    # Calculate "Difficulty Rating" candidates
    # Idea 1: Rating required to solve in Median Time of all solvers? 
    # (This is circular, but gives a baseline)
    median_t = np.median(times)
    # ln(median_t) = a * R + b => R = (ln(median_t) - b) / a
    if a_log != 0:
        r_median = (np.log(median_t) - b_log) / a_log
        print(f"Rating for Median Time ({median_t:.1f}m): {r_median:.0f}")
        
    # Idea 2: Rating required to solve in 60 minutes (if applicable)
    if a_log != 0:
        r_60 = (np.log(60) - b_log) / a_log
        print(f"Rating for 60 min: {r_60:.0f}")
        
    print("")

def main():
    csv_file = ANALYSIS_DIR / "contest_2164_analysis.csv"
    data, fieldnames = read_data(csv_file)
    problem_indices = [f for f in fieldnames if f not in ['handle', 'rating']]
    
    print("Analysis based on Log-Linear Model: T = C * e^(k * Rating)")
    print("Filtering: Rating >= 1200, Outliers removed (1.5 IQR)\n")
    
    for p_idx in problem_indices:
        ratings, times = filter_data(data, p_idx, min_rating=1200)
        ratings, times = remove_outliers(ratings, times)
        analyze_problem(p_idx, ratings, times)

if __name__ == "__main__":
    main()
