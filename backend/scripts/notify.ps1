$process = Get-WmiObject Win32_Process -Filter "name='python.exe'" | Where-Object { $_.CommandLine -like '*train_xgboost.py*' }
if ($process) {
    Wait-Process -Id $process.ProcessId
}
Add-Type -AssemblyName PresentationFramework
[System.Windows.MessageBox]::Show('XGBoost Training Complete!', 'Invexo Notification')
