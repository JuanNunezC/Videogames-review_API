import os, json
import firebase_admin
from firebase_admin import credentials

service_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")

if not firebase_admin._apps:
    if not service_json:
        raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_JSON not set")
    cred = credentials.Certificate(json.loads(service_json))
    firebase_admin.initialize_app(cred)