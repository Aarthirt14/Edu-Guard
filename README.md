# 🛡️ EduGuard AI — Student Dropout Prevention System

A full-stack AI-powered system that predicts student dropout risk using a **dual ML model architecture**.

---

## 🤖 ML Architecture

### Model 1 — Early Risk (Admission Day)
| | Details |
|--|--|
| Algorithm | RandomForest Classifier |
| Training Data | `students_static.csv` — **10,000 rows** |
| Features | Family income, scholarship, education loan, parent occupation/education, home location, HS grade, admission quota |
| Accuracy | **82%** · AUC-ROC: **0.90** |
| When it runs | Once at admission — `baseline_risk_score` stored permanently |
| Who uploads | Admin only |

### Model 2 — Dynamic Risk (Weekly)
| | Details |
|--|--|
| Algorithm | GradientBoosting Classifier |
| Training Data | `engineered_training_data.csv` — **10,000 rows** |
| Features | Attendance slope, 4-week avg, total drop, IA marks, backlog growth, fee status, weeks tracked + background from Model 1 |
| Accuracy | **95%** · AUC-ROC: **0.99** |
| When it runs | Every week after faculty CSV upload |
| Who uploads | Faculty (7 columns only) |

### Blended Dashboard Score
```
Weeks 1–2:   60% Early  +  40% Dynamic
Weeks 3–7:   40% Early  +  60% Dynamic
Weeks 8+:    20% Early  +  80% Dynamic
```

---

## 🚀 Quick Start

### 1. Backend Setup
```bash
cd backend
pip install -r requirements.txt
```

Copy and configure environment:
```bash
cp .env.example .env
# Edit .env — set SECRET_KEY, ANTHROPIC_API_KEY (optional), etc.
```

Start the server:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

On first startup, the backend automatically:
- Creates the SQLite database
- Seeds sample users and students  
- Generates both 10,000-row training datasets
- Trains both ML models and saves them

### 2. Frontend Setup
Open `frontend/login.html` in a browser (or serve with any HTTP server):

```bash
# Using Python:
cd frontend
python3 -m http.server 5500

# Or using VS Code Live Server on login.html
```

Visit: `http://localhost:5500/login.html`

---

## 🔑 Demo Credentials

| Role | Email | Password | Access |
|------|-------|----------|--------|
| Admin | admin@eduguard.com | admin123 | Full dashboard, all students, analytics |
| Faculty | faculty@eduguard.com | faculty123 | Own class (CS-A) only |
| Counselor | counselor@eduguard.com | counselor123 | Students + intervention management |
| Student | student@eduguard.com | student123 | Own profile only |

---

## 📁 Project Structure

```
eduguard_combined/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI entry point
│   │   ├── ml/
│   │   │   ├── generate_datasets.py   # Generates 10,000-row training CSVs
│   │   │   ├── train_models.py        # Trains Model 1 + Model 2
│   │   │   ├── model.py               # Prediction + blending logic
│   │   │   ├── data/
│   │   │   │   ├── students_static.csv          (10,000 rows)
│   │   │   │   └── engineered_training_data.csv (10,000 rows)
│   │   │   ├── early_risk_model.pkl   # Trained Model 1
│   │   │   └── dynamic_risk_model.pkl # Trained Model 2
│   │   ├── api/routes/
│   │   │   ├── auth.py, students.py, interventions.py
│   │   │   ├── analytics.py, reports.py, ai_chat.py
│   │   ├── models/       # SQLAlchemy DB models
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── services/     # Business logic
│   │   ├── core/         # Config + security
│   │   └── db/           # Database + seed data
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── login.html         # Login page
    ├── index.html         # Main dashboard
    ├── app.js             # All frontend logic + mock data
    ├── auth.js            # Auth — connects to backend, falls back to mock
    └── styles.css         # All styles
```

---

## 🌐 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Authenticate (returns JWT) |
| GET | `/api/students/high-risk` | High-risk students (role-filtered) |
| POST | `/api/students/predict` | Run ML risk prediction |
| GET | `/api/students/{id}` | Student detail |
| GET | `/api/analytics/dashboard` | Dashboard stat cards |
| GET | `/api/analytics/` | Charts data |
| POST | `/api/analytics/ai-chat` | AI assistant |
| POST | `/api/interventions/` | Assign intervention |
| GET | `/api/reports/export` | Export Excel/PDF |

Full API docs at: `http://localhost:8000/docs`

---

## ⚙️ Environment Variables

```env
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///./eduguard.db
ANTHROPIC_API_KEY=sk-ant-...          # Optional — enables real AI chat
ALLOWED_ORIGINS=http://localhost:5500
HIGH_RISK_THRESHOLD=70
```

---

## 🔄 Frontend ↔ Backend Mode

The frontend (`auth.js`) automatically:
1. **Tries the real backend** first on login
2. **Falls back to mock data** if backend is offline

This means the frontend works standalone without the backend running.

---

## 🧑‍💻 Re-training Models

To retrain with fresh data:
```bash
cd backend
python -m app.ml.train_models
```

To regenerate datasets first:
```bash
python -m app.ml.generate_datasets
python -m app.ml.train_models
```
