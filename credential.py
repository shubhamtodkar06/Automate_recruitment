import os

# Debug environment variables
account_id = os.getenv("ZOOM_ACCOUNT_ID")
client_id = os.getenv("ZOOM_CLIENT_ID")
client_secret = os.getenv("ZOOM_CLIENT_SECRET")

if not account_id:
    print("ZOOM_ACCOUNT_ID is missing")
if not client_id:
    print("ZOOM_CLIENT_ID is missing")
if not client_secret:
    print("ZOOM_CLIENT_SECRET is missing")

raise ValueError("Environment variables check completed. Ensure all are set.")