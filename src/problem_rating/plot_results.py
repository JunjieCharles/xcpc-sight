import csv
import os
import matplotlib.pyplot as plt
import statistics
import math

from .paths import ANALYSIS_DIR, PLOTS_DIR, ensure_directory

def read_data(filename):
    data = []
    with open(filename, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data, reader.fieldnames

def process_problem_data(data, problem_index):
    ratings = []
    times = []
    
    for row in data:
        rating_str = row['rating']
        time_str = row.get(problem_index)
        
        if not rating_str or not time_str:
            continue
            
        try:
            rating = int(rating_str)
            time_sec = float(time_str)
            
            # Filter out unreasonable data if any
            if rating > 0 and time_sec >= 0:
                ratings.append(rating)
                times.append(time_sec / 60) # Convert to minutes
        except ValueError:
            continue
            
    return ratings, times

def calculate_binned_stats(ratings, times, bin_size=50):
    if not ratings:
        return [], []
        
    min_rating = min(ratings)
    max_rating = max(ratings)
    
    # Create bins
    bins = {}
    for r, t in zip(ratings, times):
        bin_key = (r // bin_size) * bin_size
        if bin_key not in bins:
            bins[bin_key] = []
        bins[bin_key].append(t)
        
    # Calculate stats for each bin
    sorted_keys = sorted(bins.keys())
    bin_centers = []
    medians = []
    
    for k in sorted_keys:
        vals = bins[k]
        if len(vals) >= 5: # Only plot bins with enough data points to be meaningful
            bin_centers.append(k + bin_size / 2)
            medians.append(statistics.median(vals))
            
    return bin_centers, medians

def plot_problem(problem_index, ratings, times, bin_centers, medians, output_dir, contest_id=None):
    plt.figure(figsize=(10, 6))
    
    # Scatter plot for raw data
    plt.scatter(ratings, times, alpha=0.15, s=10, color='gray', label='Individual Submissions')
    
    # Line plot for median trend
    plt.plot(bin_centers, medians, 'b-', linewidth=2, label='Median Time')
    plt.plot(bin_centers, medians, 'bo', markersize=4)
    
    plt.title(f'Problem {problem_index}: Rating vs Time Consumed')
    plt.xlabel('User Rating')
    plt.ylabel('Time (minutes)')
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.legend()
    
    # Set reasonable limits
    if ratings:
        plt.xlim(min(ratings) - 50, max(ratings) + 50)
    if times:
        plt.ylim(0, max(times) * 1.05) # Or maybe cap at contest duration?
        
    if contest_id:
        filename = f'contest_{contest_id}_problem_{problem_index}_rating_vs_time.png'
    else:
        filename = f'problem_{problem_index}_rating_vs_time.png'

    output_path = os.path.join(output_dir, filename)
    plt.savefig(output_path, dpi=100)
    plt.close()
    print(f"Saved plot to {output_path}")

def plot_from_csv(csv_file):
    if not os.path.exists(csv_file):
        print(f"File {csv_file} not found.")
        return

    # Try to extract contest ID from filename
    contest_id = None
    basename = os.path.basename(csv_file)
    if basename.startswith("contest_") and "_analysis.csv" in basename:
        try:
            # Assuming format contest_{id}_analysis.csv
            parts = basename.split('_')
            if len(parts) >= 2:
                contest_id = parts[1]
        except:
            pass

    output_dir = ensure_directory(PLOTS_DIR)
        
    print(f"Reading data from {csv_file}...")
    data, fieldnames = read_data(csv_file)
    
    # Identify problem columns (exclude handle, rating)
    problem_indices = [f for f in fieldnames if f not in ['handle', 'rating']]
    
    print(f"Found problems: {problem_indices}")
    
    for p_idx in problem_indices:
        print(f"Processing Problem {p_idx}...")
        ratings, times = process_problem_data(data, p_idx)
        
        if not ratings:
            print(f"No data for Problem {p_idx}, skipping.")
            continue
            
        bin_centers, medians = calculate_binned_stats(ratings, times, bin_size=50)
        
        plot_problem(p_idx, ratings, times, bin_centers, medians, output_dir, contest_id)

if __name__ == "__main__":
    # Find the latest csv file or specify one
    # For now, hardcode or search
    csv_file = ANALYSIS_DIR / "contest_2164_analysis.csv"
    plot_from_csv(csv_file)
