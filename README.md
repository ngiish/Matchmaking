Install the FirebaseSDK package
pip install firebase_admin

Create Virtual Environment
python -m venv venv

Install arequirements
pip install -r requirements.txt

Set Environment Variables:
In your terminal (ensure virtual environment is active: source venv/bin/activate):
export FIREBASE_CRED_PATH="/home/ngish/Documents/JaGedo Hackathon/JaGedoMatchMaking/firebase-credentials.json"
export FIREBASE_DATABASE_URL="https://jagedomatchmaking-default-rtdb.firebaseio.com/"
export FLASK_ENV=development

Activate Virtual Environment:
If you’re using a virtual environment (recommended):
 source venv/bin/activate

Confirm activation (prompt should show (venv)):
 which python