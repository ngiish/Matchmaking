from flask import Flask, request, jsonify, render_template
import pandas as pd
import json
import os
from math import radians, sin, cos, sqrt, atan2
from firebase_admin import credentials, db, initialize_app
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman

# Initialize Firebase
cred_path = os.getenv("FIREBASE_CRED_PATH", "/home/ngish/Documents/JaGedo Hackathon/JaGedoMatchMaking/firebase-credentials.json")
cred = credentials.Certificate(cred_path)
firebase_url = os.getenv("FIREBASE_DATABASE_URL", "https://jagedomatchmaking-default-rtdb.firebaseio.com/")
initialize_app(cred, {"databaseURL": firebase_url})

app = Flask(__name__)
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])
limiter.init_app(app)
Talisman(app, force_https=False)  # Set force_https=True for Render

# Initialize Firebase data (run once, then comment out)
def init_firebase_data():
    ref = db.reference("artisans")
    ref.set({
        "availability": {
            "1": True,
            "2": False,
            "3": True,
            "4": True,
            "5": False
        },
        "locations": {
            "1": {"lat": -1.2921, "long": 36.8219},
            "2": {"lat": -1.3032, "long": 36.8012},
            "3": {"lat": -1.2800, "long": 36.8300},
            "4": {"lat": -1.2950, "long": 36.8150},
            "5": {"lat": -1.2870, "long": 36.8250}
        }
    })
# init_firebase_data()  # Uncomment to run once, then comment out

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius (km)
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def get_availability(artisan_ids):
    ref = db.reference("artisans/availability")
    statuses = ref.get() or {}
    return {id: statuses.get(str(id), False) for id in artisan_ids}

def get_locations(artisan_ids):
    ref = db.reference("artisans/locations")
    locations = ref.get() or {}
    return {id: locations.get(str(id), {"lat": 0, "long": 0}) for id in artisan_ids}

def match_artisans(job_type, user_lat, user_long):
    artisans = pd.read_csv("artisans.csv")
    artisans["skills"] = artisans["skills"].apply(json.loads)
    artisans["skill_score"] = artisans["skills"].apply(lambda x: 1 if job_type in x else 0)
    locations = get_locations(artisans["id"].tolist())
    artisans["lat"] = artisans["id"].apply(lambda x: locations[x]["lat"])
    artisans["long"] = artisans["id"].apply(lambda x: locations[x]["long"])
    artisans["distance"] = artisans.apply(
        lambda x: haversine(user_lat, user_long, x["lat"], x["long"]), axis=1)
    artisans = artisans[artisans["distance"] <= 20]
    if artisans.empty:
        return pd.DataFrame()
    artisans["proximity_score"] = 1 - artisans["distance"] / 20
    artisans["rating_score"] = artisans["rating"] / 5
    artisans["response_score"] = 1 - artisans["responseTime"] / 60
    artisans["total_score"] = (0.4 * artisans["skill_score"] +
                                0.3 * artisans["rating_score"] +
                                0.2 * artisans["response_score"] +
                                0.1 * artisans["proximity_score"])
    availability = get_availability(artisans["id"].tolist())
    artisans["available"] = artisans["id"].apply(lambda x: availability.get(x, False))
    return artisans.sort_values("total_score", ascending=False).head(5)

def validate_input(job_type, lat, long):
    valid_job_types = ["plumbing", "electrical", "carpentry"]
    if not job_type or job_type not in valid_job_types:
        return False, "Invalid job type"
    if not isinstance(lat, (int, float)) or not (-90 <= lat <= 90):
        return False, "Invalid latitude"
    if not isinstance(long, (int, float)) or not (-180 <= long <= 180):
        return False, "Invalid longitude"
    return True, None

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/results", methods=["POST"])
@limiter.limit("10 per minute")
def results():
    job_type = request.form.get("jobType")
    try:
        lat = float(request.form.get("lat"))
        long = float(request.form.get("long"))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid coordinates"}), 400
    is_valid, error = validate_input(job_type, lat, long)
    if not is_valid:
        return jsonify({"error": error}), 400
    artisans = match_artisans(job_type, lat, long)
    return render_template("results.html", artisans=artisans.to_dict(orient="records") if not artisans.empty else [])

@app.route("/match", methods=["POST"])
@limiter.limit("10 per minute")
def match():
    data = request.json
    job_type = data.get("jobType")
    try:
        lat = float(data.get("lat"))
        long = float(data.get("long"))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid coordinates"}), 400
    is_valid, error = validate_input(job_type, lat, long)
    if not is_valid:
        return jsonify({"error": error}), 400
    results = match_artisans(job_type, lat, long)
    if results.empty:
        return jsonify([]), 200
    return jsonify(results[["id", "name", "skills", "rating", "distance", "available"]].to_dict(orient="records"))

if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_ENV", "development") == "development")