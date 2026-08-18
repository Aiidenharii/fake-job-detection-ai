import re, os, joblib
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

MODEL_PATH = Path(__file__).resolve().parent / "model.joblib"

SUSPICIOUS = [
    "registration fee","processing fee","pay to apply","pay money","guaranteed income",
    "instant joining","no interview","earn money quickly","make money fast",
    "urgent hiring","limited seats","send otp","bank details","credit card",
    "security deposit","training fee","work from home","easy money"
]

# Small fallback training corpus so the application works immediately.
TRAIN_X = [
    "software engineer at established company, interview required, salary based on experience",
    "data analyst role, technical interview, office location, benefits and qualifications listed",
    "backend developer, bachelor's degree, two interviews, company website and recruiter email",
    "marketing manager, experience required, normal application process and job responsibilities",
    "pay registration fee and get guaranteed income, no interview, instant joining",
    "urgent hiring earn money quickly send bank details and processing fee",
    "work from home easy money no experience required pay security deposit",
    "send money for training and receive guaranteed job immediately"
]
TRAIN_Y = [0,0,0,0,1,1,1,1]

def load_model():
    if MODEL_PATH.exists():
        return joblib.load(MODEL_PATH)
    model = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1,2), min_df=1, sublinear_tf=True)),
        ("clf", LogisticRegression(max_iter=1000, random_state=42))
    ])
    model.fit(TRAIN_X, TRAIN_Y)
    joblib.dump(model, MODEL_PATH)
    return model

MODEL = load_model()

def analyze_text(text):
    clean = text.lower()
    proba = float(MODEL.predict_proba([clean])[0][1])
    keywords = sorted({k for k in SUSPICIOUS if k in clean})

    factors=[]
    for k in keywords:
        points = 8 if any(w in k for w in ["fee","pay","bank","otp","deposit","credit"]) else 5
        factors.append({"name":f"Suspicious phrase detected: {k}","severity":"high" if points>=8 else "medium","points":points})

    if re.search(r"!{2,}|\${3,}|₹\s*\d{6,}", text):
        factors.append({"name":"Excessive promotional or money-related formatting","severity":"medium","points":5})

    if len(text.split()) < 35:
        factors.append({"name":"Very short job description","severity":"medium","points":7})

    raw_signal = min(25, len(keywords)*5 + (7 if len(text.split()) < 35 else 0) + (5 if re.search(r"!{2,}",text) else 0))
    return {
        "fake_probability": round(proba*100,1),
        "nlp_signal_score": raw_signal,
        "keywords": keywords,
        "factors": factors,
        "model_name":"TF-IDF + Logistic Regression"
    }
