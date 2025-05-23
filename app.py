from flask import Flask, request, jsonify, render_template, g
import secrets
from flask_talisman import Talisman
import pandas as pd
import numpy as np
from sklearn.preprocessing import OneHotEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import firebase_admin
from firebase_admin import credentials, db
import logging
import os

# Initialize Flask app
app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Configure Talisman with CSP
talisman = Talisman(app, content_security_policy={
    'default-src': "'self'",
    'script-src': "'self'"
}, content_security_policy_nonce_in=['script-src'])

# Custom function to generate a secure nonce
@app.before_request
def generate_nonce():
    g.nonce = secrets.token_urlsafe(16)
    logger.debug(f"Generated nonce for request: {g.nonce}")

# DEBUG: Print CSP header to confirm nonce is applied
@app.after_request
def debug_csp_header(response):
    csp = response.headers.get("Content-Security-Policy")
    if csp:
        logger.debug(f"CSP Header: {csp}")
        # Verify nonce in CSP matches g.nonce
        if f"'nonce-{g.nonce}'" not in csp:
            logger.warning(f"Nonce mismatch: g.nonce={g.nonce}, CSP={csp}")
    return response


# Firebase setup
cred = credentials.Certificate("/home/ngish/Documents/JaGedo Hackathon/JaGedoMatchMaking/firebase-credentials.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://jagedomatchmaking-default-rtdb.europe-west1.firebasedatabase.app/'
})
ref = db.reference('/artisans')

# Define expected files
DATA_DIR = "/home/ngish/Documents/JaGedo Hackathon/JaGedoMatchMaking/"
CLIENT_FILE = os.path.join(DATA_DIR, "cleaned_dataset_client.csv")
PROFESSIONALS_FILE = os.path.join(DATA_DIR, "cleaned_dataset_professionals.csv")

# Load datasets dynamically
df_clients = None
df_professionals = None

if os.path.exists(CLIENT_FILE):
    try:
        df_clients = pd.read_csv(CLIENT_FILE)
        logger.info(f"Loaded client dataset with columns: {list(df_clients.columns)}")
    except Exception as e:
        logger.error(f"Failed to load client dataset: {str(e)}")
else:
    logger.warning(f"Client dataset not found at {CLIENT_FILE}. Proceeding without client data.")

if os.path.exists(PROFESSIONALS_FILE):
    try:
        df_professionals = pd.read_csv(PROFESSIONALS_FILE)
        logger.info(f"Loaded professionals dataset with columns: {list(df_professionals.columns)}")
    except Exception as e:
        logger.error(f"Failed to load professionals dataset: {str(e)}")
else:
    logger.error(f"Professionals dataset not found at {PROFESSIONALS_FILE}. Cannot proceed without professionals data.")
    raise FileNotFoundError(f"Required file {PROFESSIONALS_FILE} not found.")

# Define required and optional columns
REQUIRED_PROF_COLUMNS = ['Name', 'Profession', 'County']  # Minimum columns needed for matching
OPTIONAL_PROF_COLUMNS = ['Gender', 'Rating', 'Response Time', 'Customer Satisfaction']  # Used if available
AVAILABLE_PROF_COLUMNS = list(df_professionals.columns)

# Ensure required columns exist
missing_required = [col for col in REQUIRED_PROF_COLUMNS if col not in AVAILABLE_PROF_COLUMNS]
if missing_required:
    logger.error(f"Professionals dataset missing required columns: {missing_required}")
    raise ValueError(f"Professionals dataset missing required columns: {missing_required}")

# Map response time and satisfaction if columns exist
response_time_map = {'Below 1 hour': 1, '2–3 hours': 2, '4–5 hours': 3, '6–10 hours': 4, 'More than 10 hours': 5, 'Above 12 hours': 5}
satisfaction_map = {'Excellent': 3, 'Good': 2, 'Fair': 1, 'Bad': 0}

if 'Response Time' in AVAILABLE_PROF_COLUMNS:
    df_professionals['Response Time Encoded'] = df_professionals['Response Time'].map(lambda x: response_time_map.get(x, 5) if pd.notna(x) else 5)
else:
    df_professionals['Response Time Encoded'] = 5  # Default value if column missing
    logger.warning("Response Time column not found in professionals dataset. Using default value 5.")

if 'Customer Satisfaction' in AVAILABLE_PROF_COLUMNS:
    df_professionals['Customer Satisfaction Encoded'] = df_professionals['Customer Satisfaction'].map(lambda x: satisfaction_map.get(x, 1) if pd.notna(x) else 1)
else:
    df_professionals['Customer Satisfaction Encoded'] = 1  # Default value if column missing
    logger.warning("Customer Satisfaction column not found in professionals dataset. Using default value 1.")

# Use available categorical features for encoding
categorical_features = ['Profession', 'County']
if 'Gender' in AVAILABLE_PROF_COLUMNS:
    categorical_features.append('Gender')

# Prepare data for ML model
if df_clients is not None:
    combined = pd.concat([df_clients[categorical_features], df_professionals[categorical_features]], axis=0)
else:
    combined = df_professionals[categorical_features]
    logger.warning("No client data available. Using only professionals data for encoding.")

encoder = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
encoder.fit(combined)

if df_clients is not None:
    client_features = encoder.transform(df_clients[categorical_features])
else:
    client_features = None
professional_features = encoder.transform(df_professionals[categorical_features])

# Prepare ML target
if df_clients is not None:
    df_clients['target'] = 0
    for i in range(len(df_clients)):
        client_prof = df_clients.iloc[i]['Profession']
        matches = df_professionals['Profession'] == client_prof
        df_clients.loc[i, 'target'] = 1 if matches.any() else 0
    logger.info(f"Unique target values: {df_clients['target'].unique()}")

    y = []
    for prof in df_professionals['Profession']:
        matches = df_clients['Profession'] == prof
        y.append(1 if matches.any() else 0)
    y = np.array(y)
else:
    y = np.ones(len(df_professionals))  # Default: assume all professionals are potential matches
    logger.warning("No client data available. Assuming all professionals are potential matches for ML model.")

# Prepare features for ML model
feature_columns = list(encoder.get_feature_names_out(categorical_features))
if 'Rating' in AVAILABLE_PROF_COLUMNS:
    feature_columns.append('Rating')
feature_columns.extend(['Response Time Encoded', 'Customer Satisfaction Encoded'])

X_pro = pd.concat([pd.DataFrame(professional_features, columns=encoder.get_feature_names_out(categorical_features)),
                   df_professionals[[col for col in ['Rating', 'Response Time Encoded', 'Customer Satisfaction Encoded'] if col in df_professionals.columns]]],
                  axis=1).fillna(0)

# Reset indices to ensure alignment
df_professionals = df_professionals.reset_index(drop=True)
X_pro = X_pro.reset_index(drop=True)

if len(np.unique(y)) > 1:
    X_train, X_test, y_train, y_test = train_test_split(X_pro, y, test_size=0.2, random_state=42)
    rf_model = RandomForestClassifier(n_estimators=100, random_state=42)
    rf_model.fit(X_train, y_train)
    ml_scores = rf_model.predict_proba(X_pro)[:, 1]
else:
    logger.warning("Only one class detected in target. Using dummy scores.")
    ml_scores = np.zeros(len(X_pro))

# Ensure ml_scores aligns with df_professionals
ml_scores = ml_scores[:len(df_professionals)]

def match_artisans(job_type, location):
    try:
        filtered_pros = df_professionals[df_professionals['Profession'] == job_type].copy()
        if len(filtered_pros) == 0:
            logger.info(f"No professionals found for jobType: {job_type}")
            return []

        try:
            availability = ref.child('availability').get() or {}
            logger.debug(f"Firebase availability data: {availability}")
        except firebase_admin.exceptions.NotFoundError as e:
            logger.error(f"Firebase error: {str(e)}. Assuming all professionals are available.")
            availability = {}
        except Exception as e:
            logger.error(f"Unexpected Firebase error: {str(e)}. Assuming all professionals are available.")
            availability = {}

        results = []
        for idx in filtered_pros.index:
            pro = filtered_pros.loc[idx]
            logger.debug(f"Processing professional at index {idx}: {pro['Name']}")
            pro_id = pro['Name'].split('_')[1]
            same_county = 1 if pro['County'].lower() == location.lower() else 0
            is_available = availability.get(pro_id, True)
            if not is_available:
                logger.debug(f"Professional {pro['Name']} is not available")
                continue
            if idx >= len(ml_scores):
                logger.warning(f"Index {idx} exceeds ml_scores length ({len(ml_scores)}). Skipping.")
                continue
            match_score = ml_scores[idx]
            combined_score = 0.6 * match_score + 0.4 * same_county

            # Build result dynamically based on available columns
            result = {
                'id': pro_id,
                'name': pro['Name'],
                'profession': pro['Profession'],
                'county': pro['County'],
                'available': is_available,
                'match_score': round(combined_score, 3)
            }
            if 'Rating' in AVAILABLE_PROF_COLUMNS:
                result['rating'] = pro['Rating']
            if 'Response Time' in AVAILABLE_PROF_COLUMNS:
                result['response_time'] = pro['Response Time']
            if 'Customer Satisfaction' in AVAILABLE_PROF_COLUMNS:
                result['satisfaction'] = pro['Customer Satisfaction']

            results.append(result)

        # Adjust sorting based on available columns
        sort_keys = [lambda x: -x['match_score'], lambda x: -int(x['county'].lower() == location.lower())]
        if 'Rating' in AVAILABLE_PROF_COLUMNS:
            sort_keys.append(lambda x: -x['rating'])
        results = sorted(results, key=lambda x: tuple(f(x) for f in sort_keys))
        logger.info(f"Found {len(results)} matching professionals")
        return results[:3] if len(results) >= 3 else results + [None] * (3 - len(results))
    except Exception as e:
        logger.error(f"Error in match_artisans: {str(e)}")
        raise

@app.route('/')
def index():
    if not hasattr(g, 'nonce'):
        logger.error("Nonce not generated for this request")
        g.nonce = secrets.token_urlsafe(16)
    logger.debug(f"Rendering index.html with nonce: {g.nonce}")
    return render_template('index.html', nonce=g.nonce)

@app.route('/match', methods=['POST'])
def get_matches():
    try:
        data = request.get_json()
        if not data:
            logger.error("No JSON data received in request")
            return jsonify({'error': 'No data provided'}), 400

        job_type = data.get('jobType', '')
        location = data.get('location', 'Nairobi')
        if not job_type:
            logger.error("Missing jobType in request")
            return jsonify({'error': 'jobType is required'}), 400

        matches = match_artisans(job_type, location)
        matches = [m for m in matches if m is not None]
        return jsonify(matches)
    except Exception as e:
        logger.error(f"Error in /match endpoint: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)