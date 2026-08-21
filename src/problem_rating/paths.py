from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCAL_DATA_DIR = PROJECT_ROOT / "data-cache" / "problem-rating"
RAW_DATA_DIR = LOCAL_DATA_DIR / "data" / "raw"
API_CACHE_DIR = RAW_DATA_DIR / "api_cache"
PROCESSED_DATA_DIR = LOCAL_DATA_DIR / "data" / "processed"
ANALYSIS_DIR = LOCAL_DATA_DIR / "outputs" / "analysis"
PLOTS_DIR = LOCAL_DATA_DIR / "outputs" / "plots"
MODEL_DIR = LOCAL_DATA_DIR / "outputs" / "models"
MODEL_FILE = MODEL_DIR / "time_model.json"
PROBLEM_FEATURE_FILE = PROCESSED_DATA_DIR / "problem_features.csv"


def ensure_directory(directory: Path) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    return directory
