# 🛡️ EduGuard AI — Student Dropout Prevention System

Predicting dropout risk before it becomes dropout reality — using dual ML models, blended risk scoring, and an autonomous AI Copilot.

---

## What It Does
EduGuard is a full-stack agentic AI system that gives institutions a proactive early-warning engine for student dropout. Rather than reacting to failing grades, it monitors both baseline socio-economic vulnerability and real-time behavioral shifts — flagging at-risk students weeks before intervention becomes urgent.

---

## 🤖 ML Architecture
EduGuard runs two independent classifiers and dynamically blends their scores as the semester progresses.

| | Model 1 — Early Risk | Model 2 — Dynamic Risk |
|---|---|---|
| **Algorithm** | RandomForest | GradientBoosting |
| **Trained on** | 10,000 baseline records | 10,000 longitudinal records |
| **Input features** | Family income, parental education, scholarship status, home location, admission quota | Attendance slope (4-week trend), internal marks trajectory, backlog accumulation, fee payment status |
| **Trigger** | At admission | Weekly (faculty data upload) |
| **Purpose** | Detect socio-economic risk at entry | Detect sudden behavioral risk spikes |

**Blended Scoring** — Weights shift from 60/40 (baseline/dynamic) early in the semester to 20/80 by the end, reflecting the increasing signal quality of behavioral data over time.

---

## 🌟 Key Features

### Role-Based Portals
Four dedicated dashboards, each scoped to a distinct workflow:
- **Admin** — Institution-wide risk trends, financial support management, AI Copilot controls
- **Faculty** — Class-level monitoring, attendance/marks uploads, student account management
- **Counselor** — Intervention queue, risk trend diagnostics per student, session scheduling
- **Student** — Personal risk transparency, scholarship guidance, help request channel

### AI Agent Copilot
An autonomous backend engine that runs continuously:
- Scans for risk escalations across the student database
- Auto-generates structured **Action Tickets** for high-priority cases
- Produces LLM-driven **Intervention Strategies** (e.g., "Marks dropped 20% while attendance is stable — recommend academic peer-mentorship")
- Integrates with external workflows via Slack / n8n / Email

### Financial Support Hub
Bridges students at financial risk directly to institutional support:
- Students submit income, parent occupation, and preferred aid type (installment plan vs. scholarship)
- Admins review AI-annotated cases and publish custom support plans to student portals

### Reporting
- **High Risk PDF Summary** — Stakeholder-ready reports with risk breakdowns
- **Intervention Tracker (Excel)** — Audit trail for counselor actions
- **Monthly Trend Reports** — Longitudinal efficacy analysis

---

## 🚀 Quick Start

### Backend
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Add your ANTHROPIC_API_KEY or GOOGLE_AI_STUDIO_API_KEY to .env
uvicorn app.main:app --reload
```
On first run, the backend auto-generates 20,000 rows of synthetic training data and trains both models.

### Frontend
```bash
cd frontend
python -m http.server 5500
```
- Landing page → `http://localhost:5500/`
- Dashboard → `http://localhost:5500/dashboard.html`

---

## 🔑 Demo Credentials

| Role | Username | Password |
|---|---|---|
| Admin | `admin@eduguard.com` | `admin123` |
| Faculty | `faculty@eduguard.com` | `faculty123` |
| Counselor | `counselor@eduguard.com` | `counselor123` |
| Student | `student@eduguard.com` | `student123` |

---

## ⚙️ Environment Variables

| Variable | Description |
|---|---|
| `AI_BACKEND` | `gemini` (recommended) or `ollama` |
| `GOOGLE_AI_STUDIO_API_KEY` | API key from Google AI Studio |
| `ANTHROPIC_API_KEY` | Anthropic API key (if using Claude backend) |
| `DATABASE_URL` | SQLite path (defaults to local file) |
| `EDU_GUARD_API_URL` | Frontend config pointing to the backend URL |

---

## 📁 Project Structure
```
eduguard_combined/
├── backend/
│   └── app/
│       ├── main.py           # FastAPI entry point
│       ├── ml/               # Dual ML model training & inference
│       ├── api/routes/       # Auth, Students, AI Chat, Reports
│       ├── services/         # AI Copilot & business logic
│       └── core/             # Config & security
├── frontend/
│   ├── index.html            # Marketing landing page
│   ├── dashboard.html        # SPA app shell
│   ├── login.html            # Authentication
│   ├── app.js                # Dashboard & charting logic
│   └── auth.js               # Token & role management
└── render.yaml               # One-click cloud deployment config
```

---

## 🛠️ Tech Stack
- **Layer**: Technology
- **Backend**: FastAPI, Python
- **ML**: scikit-learn (RandomForest, GradientBoosting)
- **AI Copilot**: Claude (Anthropic) / Gemini (Google)
- **Frontend**: Vanilla JS, HTML/CSS
- **Database**: SQLite
- **Reports**: ReportLab (PDF), openpyxl (Excel)
- **Deployment**: Render (render.yaml)

---

Built as a complete agentic AI solution for educational resilience.
