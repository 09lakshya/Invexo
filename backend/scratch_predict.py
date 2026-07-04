import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.services.ai.prediction_service import PredictionService

print("Running local PredictionService check for RELIANCE.NS...")
try:
    res = PredictionService.predict_stock("RELIANCE.NS")
    print("\n--- PREDICTION RESULT ---")
    import json
    print(json.dumps(res, indent=2))
except Exception as e:
    import traceback
    traceback.print_exc()
