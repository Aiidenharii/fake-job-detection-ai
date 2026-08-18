from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
from pydantic import BaseModel
from pathlib import Path
import re, os, math
from .ml import analyze_text

BASE = Path(__file__).resolve().parent
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./fakejobs.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
ALGORITHM = "HS256"
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(30), default="user")
    created_at = Column(DateTime, default=datetime.utcnow)

class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String(255))
    company = Column(String(255))
    description = Column(Text)
    salary = Column(String(120))
    location = Column(String(120))
    recruiter_email = Column(String(255))
    company_website = Column(String(500))
    application_url = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)

class Prediction(Base):
    __tablename__ = "predictions"
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    prediction = Column(String(50))
    fake_probability = Column(Float)
    legitimate_probability = Column(Float)
    risk_score = Column(Float)
    risk_level = Column(String(20))
    model_name = Column(String(100))
    explanation = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Fake Job Detection API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

class Register(BaseModel):
    name: str
    email: str
    password: str

class Login(BaseModel):
    email: str
    password: str

class AnalyzeRequest(BaseModel):
    title: str = ""
    company: str = ""
    description: str
    salary: str = ""
    location: str = ""
    recruiter_email: str = ""
    company_website: str = ""
    application_url: str = ""

def db():
    d = SessionLocal()
    try:
        yield d
    finally:
        d.close()

def token_for(user):
    return jwt.encode({"sub": str(user.id), "exp": datetime.utcnow()+timedelta(hours=8)}, SECRET_KEY, algorithm=ALGORITHM)

def current_user(token: str, d: Session):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uid = int(payload["sub"])
        user = d.get(User, uid)
        if not user: raise ValueError()
        return user
    except Exception:
        raise HTTPException(401, "Invalid or expired token")

def company_signals(req):
    signals, score = [], 0
    if not req.company.strip():
        signals.append({"name":"Missing company name","severity":"medium","points":10}); score += 10
    if req.company_website:
        domain = re.sub(r"^https?://", "", req.company_website).split("/")[0].lower()
        if req.recruiter_email and "@" in req.recruiter_email:
            email_domain = req.recruiter_email.split("@")[-1].lower()
            if email_domain != domain and not email_domain.endswith("." + domain):
                signals.append({"name":"Recruiter email does not match website domain","severity":"medium","points":10}); score += 10
            else:
                signals.append({"name":"Recruiter email matches website domain","severity":"low","points":-5}); score -= 5
    else:
        signals.append({"name":"Company website unavailable","severity":"medium","points":8}); score += 8
    return max(0, min(25, score)), signals

@app.get("/api/health")
def health():
    return {"status":"ok"}

@app.post("/api/auth/register")
def register(x: Register, d: Session = Depends(db)):
    if d.query(User).filter(User.email == x.email.lower()).first():
        raise HTTPException(400, "Email already registered")
    u = User(name=x.name, email=x.email.lower(), password_hash=pwd.hash(x.password))
    d.add(u); d.commit(); d.refresh(u)
    return {"token": token_for(u), "user":{"id":u.id,"name":u.name,"email":u.email}}

@app.post("/api/auth/login")
def login(x: Login, d: Session = Depends(db)):
    u = d.query(User).filter(User.email == x.email.lower()).first()
    if not u or not pwd.verify(x.password, u.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return {"token": token_for(u), "user":{"id":u.id,"name":u.name,"email":u.email}}

@app.post("/api/analyze-job")
def analyze(req: AnalyzeRequest, d: Session = Depends(db)):
    result = analyze_text(req.description)
    company_score, company_signals_list = company_signals(req)

    completeness = 0
    if req.title: completeness += 3
    if req.company: completeness += 3
    if req.location: completeness += 2
    if req.salary: completeness += 2

    # Weighted transparent risk engine
    risk = (
        result["fake_probability"] * 0.55 +
        result["nlp_signal_score"] * 0.25 +
        company_score * 0.8 +
        max(0, 10-completeness)
    )
    risk = max(0, min(100, round(risk, 1)))
    level = "HIGH" if risk >= 71 else "MEDIUM" if risk >= 31 else "LOW"

    factors = result["factors"] + company_signals_list
    explanation = "; ".join(f["name"] for f in factors[:6]) or "No major suspicious indicators detected."

    job = Job(
        title=req.title, company=req.company, description=req.description,
        salary=req.salary, location=req.location,
        recruiter_email=req.recruiter_email,
        company_website=req.company_website,
        application_url=req.application_url
    )
    d.add(job); d.commit(); d.refresh(job)
    p = Prediction(
        job_id=job.id,
        prediction="potentially_fraudulent" if risk >= 50 else "likely_legitimate",
        fake_probability=result["fake_probability"],
        legitimate_probability=round(100-result["fake_probability"],1),
        risk_score=risk, risk_level=level,
        model_name=result["model_name"], explanation=explanation
    )
    d.add(p); d.commit(); d.refresh(p)

    recommendation = {
        "LOW":"This posting contains relatively few suspicious signals. Still verify the employer before sharing sensitive information.",
        "MEDIUM":"Proceed carefully. Independently verify the company, recruiter identity and application website.",
        "HIGH":"This job contains several high-risk indicators. Avoid payments or sharing sensitive information until the employer and opportunity are independently verified."
    }[level]

    return {
        "id": p.id, "job_id": job.id, "prediction": p.prediction,
        "fake_probability": p.fake_probability,
        "legitimate_probability": p.legitimate_probability,
        "risk_score": p.risk_score, "risk_level": level,
        "model_name": p.model_name,
        "factors": factors,
        "suspicious_keywords": result["keywords"],
        "company_signals": company_signals_list,
        "recommendation": recommendation,
        "disclaimer":"AI predictions are estimates and are not definitive proof that a job or company is fraudulent."
    }

@app.get("/api/analyses")
def analyses(d: Session = Depends(db)):
    rows = d.query(Prediction).order_by(Prediction.created_at.desc()).limit(100).all()
    out=[]
    for p in rows:
        j=d.get(Job,p.job_id)
        out.append({"id":p.id,"title":j.title,"company":j.company,"risk_score":p.risk_score,
                    "risk_level":p.risk_level,"prediction":p.prediction,
                    "created_at":p.created_at.isoformat()})
    return out

@app.get("/api/analyses/{pid}")
def analysis(pid:int,d:Session=Depends(db)):
    p=d.get(Prediction,pid)
    if not p: raise HTTPException(404,"Analysis not found")
    j=d.get(Job,p.job_id)
    return {"id":p.id,"job":{"title":j.title,"company":j.company,"description":j.description,
            "salary":j.salary,"location":j.location,"recruiter_email":j.recruiter_email,
            "company_website":j.company_website,"application_url":j.application_url},
            "prediction":p.prediction,"fake_probability":p.fake_probability,
            "legitimate_probability":p.legitimate_probability,"risk_score":p.risk_score,
            "risk_level":p.risk_level,"model_name":p.model_name,
            "explanation":p.explanation}

@app.delete("/api/analyses/{pid}")
def delete_analysis(pid:int,d:Session=Depends(db)):
    p=d.get(Prediction,pid)
    if not p: raise HTTPException(404,"Analysis not found")
    d.delete(p); d.commit()
    return {"deleted":True}

@app.get("/api/dashboard/stats")
def stats(d:Session=Depends(db)):
    rows=d.query(Prediction).all()
    return {
        "total":len(rows),
        "high":sum(p.risk_level=="HIGH" for p in rows),
        "medium":sum(p.risk_level=="MEDIUM" for p in rows),
        "low":sum(p.risk_level=="LOW" for p in rows),
        "average":round(sum(p.risk_score for p in rows)/len(rows),1) if rows else 0
    }

frontend = BASE.parent.parent / "frontend"
app.mount("/", StaticFiles(directory=str(frontend), html=True), name="frontend")
