import os
import time
import json
import xgboost as xgb
from app.utils.logger import get_logger

logger = get_logger("model_loader")

_loaded_models = {}

def load_all_models():
    """Loads all XGBoost models from the models directory into memory."""
    global _loaded_models
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    models_dir = os.environ.get("RENDER_DISK_PATH", os.path.join(base_dir, "models"))
    
    if not os.path.exists(models_dir):
        logger.warning(f"Models directory not found at {models_dir}")
        return
        
    start_time = time.time()
    count = 0
    for filename in os.listdir(models_dir):
        if filename.endswith("_xgb.json"):
            symbol = filename.replace("_xgb.json", "")
            model_path = os.path.join(models_dir, filename)
            try:
                meta_path = os.path.join(models_dir, f"{symbol}_meta.json")
                r2_good = True
                if os.path.exists(meta_path):
                    with open(meta_path, 'r') as f:
                        meta_meta = json.load(f)
                        if meta_meta.get("r2", 1.0) < -0.5:
                            r2_good = False
                
                if r2_good:
                    model = xgb.XGBRegressor()
                    model.load_model(model_path)
                    _loaded_models[symbol] = model
                    count += 1
            except Exception as e:
                logger.error(f"Error pre-loading model for {symbol}: {e}")
                
    duration = time.time() - start_time
    logger.info(f"Successfully pre-loaded {count} XGBoost models in {duration:.2f} seconds.")

def load_all_models_async():
    import threading
    thread = threading.Thread(target=load_all_models)
    thread.daemon = True
    thread.start()

def get_model(symbol: str):
    """Retrieve preloaded model or load it dynamically if not cached."""
    global _loaded_models
    model_base_name = symbol.replace('.NS', '').replace('.BO', '')
    model = _loaded_models.get(model_base_name)
    if model is not None:
        return model
        
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    models_dir = os.environ.get("RENDER_DISK_PATH", os.path.join(base_dir, "models"))
    model_path = os.path.join(models_dir, f"{model_base_name}_xgb.json")
    meta_path = os.path.join(models_dir, f"{model_base_name}_meta.json")
    
    r2_good = True
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r') as f:
                meta_meta = json.load(f)
                if meta_meta.get("r2", 1.0) < -0.5:
                    r2_good = False
        except Exception:
            pass
            
    if r2_good and os.path.exists(model_path):
        try:
            model = xgb.XGBRegressor()
            model.load_model(model_path)
            _loaded_models[model_base_name] = model
            return model
        except Exception as e:
            logger.error(f"Error loading model dynamically for {symbol}: {e}")
            
    return None
