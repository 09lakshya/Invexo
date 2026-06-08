@echo off
cd /d "c:\Users\Lakshya Hindocha\OneDrive\Desktop\Invexo\backend"
echo Starting Nightly XGBoost Training...
python scripts\train_xgboost.py --all --force
echo Nightly Training Complete!
powershell -Command "(New-Object -ComObject WScript.Shell).Popup('Invexo XGBoost Nightly Training is Complete!', 10, 'Invexo ML Training', 64)"
