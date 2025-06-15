#!/usr/bin/env python3
import requests, json
from config import load, save

CENTRAL_REG_URL = "http://127.0.0.1:5090/tunnel/api/register_or_get_id/"

def main():
    cfg = load()
    if cfg.get("house_id"):
        print("Already registered:", cfg)
        return

    token = "9eLDsQYOOCiHMpPud07xIo6HNIfCrOqOB4Sive08Elk" #input("Enter one-time registration token: ").strip() 
    resp = requests.post(CENTRAL_REG_URL, json={"token": token})
    if resp.status_code != 200:
        print("Registration failed:", resp.json())
        return

    data = resp.json()  # { house_id, secret_key }
    save(data)
    print("Registered successfully!  Saved:", data)

if __name__ == "__main__":
    main()
