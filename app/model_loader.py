import joblib

from config import MODEL_PATH, MODULE_MODEL_PATH

# =========================================================
# LOAD MODELS
# =========================================================

# Main AC Power model
model = joblib.load(MODEL_PATH)

# Module Temperature model
module_temp_model = joblib.load(MODULE_MODEL_PATH)