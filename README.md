# 🛡️ EduGuard AI — Student Dropout Prevention System

A full-stack AI-powered system that predicts student dropout risk and automates intervention using a **dual ML model architecture** and **Agentic Copilot**.

---

## 🤖 Core ML Engine (Dual Architecture)

EduGuard doesn't just look at grades; it uses two separate AI models to track both baseline vulnerability and real-time behavioral changes.

### Model 1 — Early Risk (Baseline)
- **Algorithm**: RandomForest Classifier (Trained on 10,000 baseline records)
- **Features**: Family income, parental education, scholarship status, home location, and admission quota.
- **When it runs**: Immediately upon student admission.
- **Goal**: Identify students who enter the system with high socio-economic risk factors.

### Model 2 — Dynamic Risk (Behavioral)
- **Algorithm**: GradientBoosting Classifier (Trained on 10,000 behavior longitudinal records)
- **Features**: Attendance slope (4-week trend), internal marks growth/decline, backlog accumulation, and fee payment status.
- **When it runs**: Weekly, triggered by faculty data uploads.
- **Goal**: Detect sudden "risk spikes" due to recent academic or behavioral shifts.

### Blended Risk Scoring
The system dynamically blends these scores based on the academic semester progress (Shift from 60/40 early weighting to 20/80 dynamic weighting as the semester progresses).

---

## 🌟 Key Features

### 🏛️ Role-Based Portals
- **Admin Dashboard**: Full visibility into institution-wide risk trends, financial support management, and AI Copilot control.
- **Faculty Dashboard**: Individual class monitoring, attendance/marks upload, and student password management.
- **Counselor Dashboard**: Intervention queue, student profile cards with "Risk Trend Diagnostics," and session scheduling.
- **Student Portal**: Personalized risk transparency, scholarship guidance, and "Help Request" communication bridge.

### 🤖 AI Agent Copilot
Autonomous backend engine that:
- Periodically scans the student database for risk escalations.
- Generates structured **Action Tickets** for high-priority cases.
- Provides LLM-driven **Intervention Strategies** (e.g., "Student's marks dropped 20% while attendance is stable; suggest academic peer-mentorship").
- Integrates with external automations (Slack/n8n/Email).

### 💰 Financial Support Hub
A specialized bridge for students at financial risk:
- Students can input parent occupation, income bands, and preferred support types (installments vs. scholarships).
- Admins review cases with AI-suggested guidance and publish custom support plans directly to the student portal.

### 📊 Professional PDF/Excel Reports
- **High Risk Summary**: Detailed PDF reports for stakeholder meetings.
- **Intervention Progress**: Excel tracking for audit trails.
- **Monthly Trend Reports**: Longitudinal data analysis of prevention efficacy.

---

## 🚀 Quick Start (Local Development)

### 1. Backend Setup
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set GOOGLE_AI_STUDIO_API_KEY (Gemini) or ANTHROPIC_API_KEY
uvicorn app.main:app --reload
```
*Note: On first run, the backend will auto-generate 20,000 rows of training data and train the ML models automatically.*

### 2. Frontend Setup
```bash
cd frontend
# Serve with any static server (e.g., Live Server or python -m http.server)
python -m http.server 5500
```
- **Landing Page**: `http://localhost:5500/`
- **Dashboard App**: `http://localhost:5500/dashboard.html` (Accessible after login)

---

## 🔑 Demo Credentials

| Role | Username | Password |
|------|-------|----------|
| **Admin** | `admin@eduguard.com` | `admin123` |
| **Faculty** | `faculty@eduguard.com` | `faculty123` |
| **Counselor** | `counselor@eduguard.com` | `counselor123` |
| **Student** | `student@eduguard.com` | `student123` |

---

## ⚙️ Environment Variables

| Variable | Description |
|----------|-------------|
| `AI_BACKEND` | `gemini` (recommended) or `ollama` |
| `GOOGLE_AI_STUDIO_API_KEY` | API key from Google AI Studio |
| `DATABASE_URL` | SQLite path (defaults to local file) |
| `EDU_GUARD_API_URL` | Frontend config for the backend URL |

---

## 📁 Project Structure

```
eduguard_combined/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI Entry Point
│   │   ├── ml/              # Dual ML Model Core & Training
│   │   ├── api/routes/      # Auth, Students, AI Chat, Reports routers
│   │   ├── services/        # AI Copilot & Business Logic
│   │   └── core/            # Config & Security
├── frontend/
│   ├── index.html           # Landing Page (Marketing)
│   ├── dashboard.html       # App Shell (SPA Dashboard)
│   ├── login.html           # Authentication Page
│   ├── app.js               # Dashboard & Charting Logic
│   └── auth.js              # Token & Role management
└── render.yaml              # One-click cloud deployment config
```

---

## 🛡️ Preventing Student Dropout, One Data Point at a Time.
Developed as a complete Agentic AI solution for educational resilience.
