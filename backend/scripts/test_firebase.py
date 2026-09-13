import os
import firebase_admin
from firebase_admin import credentials, auth
from dotenv import load_dotenv

load_dotenv()

cred = credentials.Certificate(os.getenv("FIREBASE_CREDENTIALS_PATH"))
firebase_admin.initialize_app(cred)

# Lista los primeros 5 usuarios (debe estar vacío la primera vez)
users = auth.list_users().iterate_all()
for u in users:
    print(u.uid, u.email)

print("✅ Firebase Admin SDK configurado correctamente")