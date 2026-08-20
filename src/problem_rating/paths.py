from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
API_CACHE_DIR = RAW_DATA_DIR / "api_cache"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
ANALYSIS_DIR = PROJECT_ROOT / "outputs" / "analysis"
PLOTS_DIR = PROJECT_ROOT / "outputs" / "plots"
MODEL_DIR = PROJECT_ROOT / "outputs" / "models"
MODEL_FILE = MODEL_DIR / "time_model.json"


def ensure_directory(directory: Path) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    return directory