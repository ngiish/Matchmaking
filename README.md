Install the FirebaseSDK package
pip install firebase_admin

Create Virtual Environment
python -m venv venv

Install arequirements
pip install -r requirements.txt

Activate Virtual Environment:
If you’re using a virtual environment (recommended):
 source venv/bin/activate

Confirm activation (prompt should show (venv)):
 which python

Reinstall Virtual Environment: If the environment is corrupted, recreate it:
 rm -rf venv
 python -m venv venv
 source venv/bin/activate
 pip install scikit-learn flask flask-talisman pandas firebase-admin

Set Environment Variables:
In your terminal (ensure virtual environment is active: source venv/bin/activate):
export FIREBASE_CRED_PATH="/home/ngish/Documents/JaGedo Hackathon/JaGedoMatchMaking/firebase-credentials.json"
export FIREBASE_DATABASE_URL="https://jagedomatchmaking-default-rtdb.firebaseio.com/"
export FLASK_ENV=development

verify
echo $FIREBASE_CRED_PATH


Verify syntax:
python -m py_compile /home/ngish/Documents/JaGedo\ Hackathon/JaGedoMatchMaking/app.py

Check requirements.txt:
cat requirements.txt

Verify Installed Packages:
flask             2.0.1
flask-limiter     3.5.0
flask-talisman    1.0.0
werkzeug          2.0.3
