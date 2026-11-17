import os

# =========================================================
# AUTOMATIC DASHBOARD REFRESH
# =========================================================

REFRESH_INTERVAL = 60  # seconds

# =========================================================
# PATHS
# =========================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Main AC Power model
MODEL_PATH = os.path.join(
    BASE_DIR,
    "models",
    "solarcast_gradient_boosting.pkl"
)

# Module Temperature model
MODULE_MODEL_PATH = os.path.join(
    BASE_DIR,
    "models",
    "solarcast_module_temperature.pkl"
)

# Historical data
PLANT1_PATH = os.path.join(
    BASE_DIR,
    "data",
    "Plant_1_Generation_Data.csv"
)

# =========================================================
# LIVE WEATHER API
# =========================================================

LATITUDE = 8.4542
LONGITUDE = 124.6319

API_URL = (
    "https://api.open-meteo.com/v1/forecast"
    f"?latitude={LATITUDE}"
    f"&longitude={LONGITUDE}"
    "&current=temperature_2m,shortwave_radiation"
    "&timezone=auto"
)