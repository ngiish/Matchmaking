from flask import Flask, request, jsonify, render_template
import pandas as pd
import numpy as np
from sklearn.preprocessing import OneHotEncoder
from sklearn.metrics.pairwise import cosine_similarity
import firebase_admin
from firebase_admin import credentials, db
import logging
import os
from fuzzywuzzy import fuzz

# Initialize Flask app
app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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
    logger.error(f"Client dataset not found at {CLIENT_FILE}. Cannot proceed without client data.")
    raise FileNotFoundError(f"Required file {CLIENT_FILE} not found.")

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
REQUIRED_PROF_COLUMNS = ['Name', 'Profession', 'County']
OPTIONAL_PROF_COLUMNS = ['Gender', 'Rating', 'Response Time', 'Customer Satisfaction']
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
    df_professionals['Response Time Encoded'] = 5
    logger.warning("Response Time column not found in professionals dataset. Using default value 5.")

if 'Customer Satisfaction' in AVAILABLE_PROF_COLUMNS:
    df_professionals['Customer Satisfaction Encoded'] = df_professionals['Customer Satisfaction'].map(lambda x: satisfaction_map.get(x, 1) if pd.notna(x) else 1)
else:
    df_professionals['Customer Satisfaction Encoded'] = 1
    logger.warning("Customer Satisfaction column not found in professionals dataset. Using default value 1.")

# Use available categorical features for encoding from both datasets
categorical_features = ['Profession', 'County']
if 'Gender' in AVAILABLE_PROF_COLUMNS and 'Gender' in df_clients.columns:
    categorical_features.append('Gender')

# Prepare data for encoding using both client and professional datasets
combined = pd.concat([df_clients[categorical_features].fillna('Unknown'),
                      df_professionals[categorical_features].fillna('Unknown')], axis=0)
encoder = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
encoder.fit(combined)

# Encode professional features with additional metrics
professional_features = encoder.transform(df_professionals[categorical_features].fillna('Unknown'))
if 'Rating' in AVAILABLE_PROF_COLUMNS:
    professional_features = np.hstack((professional_features, df_professionals[['Rating']].values))
professional_features = np.hstack((professional_features, df_professionals[['Response Time Encoded', 'Customer Satisfaction Encoded']].values))

# Function to encode client request based on available client data
def encode_request(job_type, location):
    # Use the first client row as a template (assuming one client request at a time)
    client_template = df_clients.iloc[0] if not df_clients.empty else pd.Series({'Profession': job_type, 'County': location, 'Gender': 'Unknown'})
    request_data = pd.DataFrame([[client_template.get('Profession', job_type), client_template.get('County', location)] + 
                                 [client_template.get('Gender', 'Unknown') if 'Gender' in categorical_features else '']],
                                columns=categorical_features)
    request_encoded = encoder.transform(request_data.fillna('Unknown'))
    if 'Rating' in AVAILABLE_PROF_COLUMNS:
        request_encoded = np.hstack((request_encoded, np.array([[0]])))  # Default rating
    request_encoded = np.hstack((request_encoded, np.array([[5, 1]])))  # Default Response Time and Satisfaction
    return request_encoded

def match_artisans(job_type, location):
    try:
        if df_professionals is None or df_professionals.empty:
            logger.error("No professionals data available.")
            return []
        filtered_pros = df_professionals[df_professionals['Profession'] == job_type].copy()
        if len(filtered_pros) == 0:
            logger.info(f"No professionals found for jobType: {job_type}")
            return []

        # Reindex filtered professionals and corresponding features to prevent index misalignment
        filtered_indices = filtered_pros.index
        filtered_pros = filtered_pros.reset_index(drop=True)
        filtered_features = professional_features[filtered_indices]
        logger.debug(f"Filtered pros shape: {filtered_pros.shape}, Filtered features shape: {filtered_features.shape}")

        try:
            availability = ref.child('availability').get()
            if availability is None:
                logger.warning("Firebase availability data is None. Assuming all professionals are available.")
                availability = {}
        except firebase_admin.exceptions.FirebaseError as e:
            logger.error(f"Firebase error: {str(e)}. Assuming all professionals are available.")
            availability = {}
        except Exception as e:
            logger.error(f"Unexpected Firebase error: {str(e)}. Assuming all professionals are available.")
            availability = {}

        results = []
        location = location.lower() if location else ''
        request_vector = encode_request(job_type, location)
        logger.debug(f"Request vector shape: {request_vector.shape}, Filtered features shape: {filtered_features.shape}")
        similarities = cosine_similarity(request_vector, filtered_features)[0]

        for idx, pro in filtered_pros.iterrows():
            logger.debug(f"Processing professional at index {idx}: {pro.get('Name', 'Unknown')}")
            pro_id = pro.get('Name', 'Unknown').split('_')[1] if '_' in pro.get('Name', '') and len(pro.get('Name', '').split('_')) > 1 else str(idx)
            pro_county = pro.get('County', '').lower()
            # Use fuzzy matching for proximity with error handling
            if not pro_county or not location:
                same_county = 0
            else:
                try:
                    same_county = fuzz.ratio(pro_county, location) / 100.0  # Score between 0 and 1
                    if same_county < 0.6:  # Threshold for considering a match
                        same_county = 0
                except Exception as e:
                    logger.warning(f"Fuzzy matching failed for {pro_county} and {location}: {str(e)}, using 0")
                    same_county = 0
            is_available = availability.get(pro_id, True)
            if not is_available:
                logger.debug(f"Professional {pro.get('Name', 'Unknown')} is not available")
                continue

            rating = pro.get('Rating', 0)  # Default to 0 if Rating is missing
            match_score = similarities[idx] if idx < len(similarities) else 0  # Safeguard for index out of range

            result = {
                'id': pro_id,
                'name': pro.get('Name', 'Unknown'),
                'profession': pro.get('Profession', 'Unknown'),
                'county': pro.get('County', 'Unknown'),
                'available': is_available,
                'rating': rating,
                'same_county': round(same_county, 3),  # Store the fuzzy score
                'match_score': round(match_score, 3)  # Cosine similarity score
            }
            if 'Response Time' in AVAILABLE_PROF_COLUMNS:
                result['response_time'] = pro.get('Response Time', 'N/A')
            if 'Customer Satisfaction' in AVAILABLE_PROF_COLUMNS:
                result['satisfaction'] = pro.get('Customer Satisfaction', 'N/A')

            results.append(result)

        # Sort by Rating (descending), then same_county (descending), then match_score (descending)
        results.sort(key=lambda x: (-x['rating'], -x['same_county'], -x['match_score']))
        logger.info(f"Found {len(results)} matching professionals")
        return results[:3] if len(results) >= 3 else results + [None] * (3 - len(results))
    except Exception as e:
        logger.error(f"Error in match_artisans: {str(e)} with job_type={job_type}, location={location}")
        raise  # Re-raise to capture the full traceback

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/counties', methods=['GET'])
def get_counties():
    try:
        if df_professionals is None or df_professionals.empty:
            logger.error("No professionals data available.")
            return jsonify([]), 500
        counties = sorted(df_professionals['County'].dropna().unique().tolist())
        return jsonify(counties)
    except Exception as e:
        logger.error(f"Error in /counties endpoint: {str(e)}")
        return jsonify([]), 500

@app.route('/match', methods=['POST'])
def get_matches():
    try:
        data = request.get_json()
        if not data:
            logger.error("No JSON data received in request")
            return jsonify({'error': 'No data provided'}), 400

        job_type = data.get('jobType', '')
        location = data.get('location', '')
        if not job_type:
            logger.error("Missing jobType in request")
            return jsonify({'error': 'jobType is required'}), 400
        if not location:
            logger.error("Missing location in request")
            return jsonify({'error': 'location is required'}), 400

        matches = match_artisans(job_type, location)
        matches = [m for m in matches if m is not None]
        return jsonify(matches)
    except Exception as e:
        logger.error(f"Error in /match endpoint: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)