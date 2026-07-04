import requests
import json

base_url = "https://invexo-backend.onrender.com"

print("Trying login with user@gmail.com...")
try:
    login_res = requests.post(
        f"{base_url}/auth/login",
        json={"email": "user@gmail.com", "password": "mypassword"}
    )
    print("Login Status:", login_res.status_code)
    if login_res.status_code == 200:
        token_data = login_res.json()
        token = token_data.get("access_token")
        print("Logged in successfully! Token received.")
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test predict endpoint
        predict_res = requests.get(f"{base_url}/predict/RELIANCE.NS", headers=headers)
        print("Predict Status:", predict_res.status_code)
        print("Predict Response:", json.dumps(predict_res.json(), indent=2))
        
    else:
        print("Login failed:", login_res.text)
except Exception as e:
    print("Error:", e)
