import os
from firebase_admin import credentials, db, initialize_app
# Initialize Firebase
cred_path = os.getenv("FIREBASE_CRED_PATH", "/home/ngish/Documents/JaGedo Hackathon/JaGedoMatchMaking/firebase-credentials.json")
cred = credentials.Certificate(cred_path)
firebase_url = os.getenv("FIREBASE_DATABASE_URL", "https://jagedomatchmaking-default-rtdb.firebaseio.com/")
initialize_app(cred, {"databaseURL": firebase_url})
# Flask setup
# app = Flask(__name__)
# limiter = Limiter(app, key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])
# Talisman(app, force_https=False)  # Set force_https=True for Render
# # ... rest of app.py ...
# if __name__ == "__main__":
#     app.run(debug=os.getenv("FLASK_ENV", "development") == "development")