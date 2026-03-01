from typing import Any, Dict, List, Optional
import importlib
import json
import re

from sqlalchemy.orm import Session
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.core.config import settings
from app.ml.model import predict_risk
from app.models.copilot import CopilotRun, CopilotActionTicket
from app.models.intervention import (
    Intervention,
    InterventionType,
    InterventionStatus,
    InterventionOutcome,
    TimelineEvent,
)
from app.models.student import Student
from app.models.user import User
from app.services.student_service import get_risk_trend_factors

StateGraph = None
START = None
END = None
Anthropic = None

try:
    langgraph_mod = importlib.import_module("langgraph.graph")
    StateGraph = getattr(langgraph_mod, "StateGraph", None)
    START = getattr(langgraph_mod, "START", None)
    END = getattr(langgraph_mod, "END", None)
except Exception:
    StateGraph = None
    START = None
    END = None

try:
    anthropic_mod = importlib.import_module("anthropic")
    Anthropic = getattr(anthropic_mod, "Anthropic", None)
except Exception:
    Anthropic = None


AGENT_LLM_MODEL = "claude-3-5-sonnet-latest"
COPILOT_PLAYBOOK = [
    "If attendance is falling quickly (>=10 percentage points in recent weeks), prioritize counseling plus attendance contract with weekly follow-up.",
    "If fee outstanding is present with moderate/high risk, prioritize Financial Support and initiate scholarship or installment counseling within 72 hours.",
    "If IA marks are declining by >=20%, assign Academic Support with subject-wise remediation and a two-week progress checkpoint.",
    "When both financial stress and attendance decline are present, combine Financial Support + Counseling and involve family outreach if consented.",
    "Critical risk (>=85) requires immediate counselor assignment, parent/guardian communication, and a documented intervention plan within 48 hours.",
    "High risk (75-84.9) requires intervention assignment this week and trend review after one week.",
]


def _extract_json_object(raw_text: str) -> Optional[Dict[str, Any]]:
    if not raw_text:
        return None
    text = raw_text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", text)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except Exception:
            pass

    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and last > first:
        try:
            return json.loads(text[first:last + 1])
        except Exception:
            return None
    return None


def _retrieve_rag_context(query: str, top_k: int = 2) -> List[str]:
    if not query:
        return COPILOT_PLAYBOOK[:top_k]
    vectorizer = TfidfVectorizer(stop_words="english")
    doc_vectors = vectorizer.fit_transform(COPILOT_PLAYBOOK)
    query_vector = vectorizer.transform([query])
    sims = cosine_similarity(query_vector, doc_vectors).flatten()
    ranked_indices = sims.argsort()[::-1][:top_k]
    return [COPILOT_PLAYBOOK[idx] for idx in ranked_indices]


def _build_llm_prompt(row: Dict[str, Any], rag_context: List[str]) -> str:
    student = row["student"]
    factors = row.get("factors") or []
    context_block = "\n".join(f"- {c}" for c in rag_context)
    return (
        "Given the student risk profile and policy context, return ONLY valid JSON with keys: "
        "reason_summary, recommended_intervention, priority.\n\n"
        "Allowed recommended_intervention values: Counseling, Financial Support, Academic Support, Mentorship, Family Outreach.\n"
        "Allowed priority values: Critical, High, Medium.\n\n"
        f"Student ID: {student.id}\n"
        f"Student Name: {student.name}\n"
        f"Class: {student.class_name}\n"
        f"Risk Score: {float(row.get('risk_score') or 0):.1f}\n"
        f"Risk Trend: {row.get('risk_trend') or student.risk_trend or 'stable'}\n"
        f"Detected Factors: {', '.join(factors) if factors else 'none'}\n"
        f"Baseline reason: {row.get('reason_summary') or 'N/A'}\n\n"
        "Policy context:\n"
        f"{context_block}\n"
    )


def _llm_agent_decision(row: Dict[str, Any], rag_context: List[str]) -> Optional[Dict[str, str]]:
    if not settings.ANTHROPIC_API_KEY or Anthropic is None:
        return None
    try:
        client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        prompt = _build_llm_prompt(row, rag_context)
        response = client.messages.create(
            model=AGENT_LLM_MODEL,
            max_tokens=260,
            temperature=0.2,
            system="You are EduGuard Copilot policy agent. Be precise, safety-first, and output strict JSON only.",
            messages=[{"role": "user", "content": prompt}],
        )

        text_out = ""
        content = getattr(response, "content", None)
        if isinstance(content, list) and content:
            first = content[0]
            text_out = getattr(first, "text", "") if first is not None else ""
        parsed = _extract_json_object(text_out)
        if not parsed:
            return None

        return {
            "reason_summary": str(parsed.get("reason_summary") or "").strip(),
            "recommended_intervention": str(parsed.get("recommended_intervention") or "").strip(),
            "priority": str(parsed.get("priority") or "").strip(),
        }
    except Exception:
        return None


def _agentic_reasoning(actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []
    valid_interventions = {it.value for it in InterventionType}
    valid_priorities = {"Critical", "High", "Medium"}

    for row in actions:
        factors = row.get("factors") or []
        query = " ".join([
            f"risk {float(row.get('risk_score') or 0):.1f}",
            f"trend {row.get('risk_trend') or 'stable'}",
            f"factors {' '.join(factors)}",
            f"base_reason {row.get('reason_summary') or ''}",
        ])
        rag_context = _retrieve_rag_context(query, top_k=2)

        llm_decision = _llm_agent_decision(row, rag_context)
        recommended = row["recommended_intervention"]
        priority = row["priority"]
        reason_summary = row["reason_summary"]

        if llm_decision:
            llm_recommended = llm_decision.get("recommended_intervention") or ""
            llm_priority = llm_decision.get("priority") or ""
            llm_reason = llm_decision.get("reason_summary") or ""

            if llm_recommended in valid_interventions:
                recommended = llm_recommended
            if llm_priority in valid_priorities:
                priority = llm_priority
            if llm_reason:
                reason_summary = llm_reason

        enriched.append({
            **row,
            "recommended_intervention": recommended,
            "priority": priority,
            "reason_summary": reason_summary,
            "rag_context": rag_context,
        })

    return enriched


def _recommended_intervention(factors: List[str], risk_score: float) -> str:
    if risk_score >= 85:
        return InterventionType.counseling.value
    if "financial" in factors:
        return InterventionType.financial_support.value
    if "attendance" in factors or "family" in factors:
        return InterventionType.counseling.value
    return InterventionType.academic_support.value


def _priority(risk_score: float) -> str:
    if risk_score >= 85:
        return "Critical"
    if risk_score >= 75:
        return "High"
    return "Medium"


def _fetch_student_data(db: Session) -> List[Student]:
    return db.query(Student).order_by(Student.risk_score.desc()).all()


def _predict_risk_payload(students: List[Student]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for student in students:
        sem_num = int(student.semester.split()[-1]) if "Semester" in student.semester else 4
        pred = predict_risk(
            attendance=float(student.attendance or 0),
            marks=float(student.marks or 0),
            has_financial_issue=bool(student.has_financial_issue),
            has_family_issue=bool(student.has_family_issue),
            semester=sem_num,
        )
        rows.append({
            "student": student,
            "risk_score": float(pred.get("risk_score") or 0),
            "risk_level": pred.get("risk_level") or "low",
            "factors": pred.get("risk_factors") or [],
        })
    return rows


def _explain_rows(db: Session, predicted_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    explained: List[Dict[str, Any]] = []
    for row in predicted_rows:
        student: Student = row["student"]
        trend = get_risk_trend_factors(db, student.id)
        drivers = trend.get("drivers") or []
        reason = " ".join(drivers[:3]).strip() or "Risk increased due to mixed attendance/academic signals."
        explained.append({
            **row,
            "risk_trend": trend.get("attendance_trend") if trend else student.risk_trend,
            "reason_summary": reason,
        })
    return explained


def _choose_actions(explained_rows: List[Dict[str, Any]], threshold: int = 70) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    for row in explained_rows:
        if row["risk_score"] < threshold:
            continue
        intervention = _recommended_intervention(row.get("factors") or [], row["risk_score"])
        actions.append({
            **row,
            "recommended_intervention": intervention,
            "priority": _priority(row["risk_score"]),
        })
    return actions


def _ensure_intervention_and_timeline(db: Session, action_row: Dict[str, Any], actor_name: str, actor_id: str) -> None:
    student: Student = action_row["student"]
    try:
        iv_type = InterventionType(action_row["recommended_intervention"])
    except Exception:
        iv_type = InterventionType.counseling

    existing = (
        db.query(Intervention)
        .filter(
            Intervention.student_id == student.id,
            Intervention.type == iv_type,
            Intervention.status.in_([InterventionStatus.pending, InterventionStatus.active]),
        )
        .order_by(Intervention.id.desc())
        .first()
    )

    if existing:
        intervention = existing
    else:
        intervention = Intervention(
            student_id=student.id,
            type=iv_type,
            assigned_by=actor_name,
            assigned_by_id=actor_id,
            status=InterventionStatus.pending,
            outcome=InterventionOutcome.none,
            notes=f"Auto-created by Early Warning Copilot ({action_row['priority']} priority).",
        )
        db.add(intervention)
        db.flush()

    clean_reason = re.sub(r"\s*\[RAG:[\s\S]*?\]\s*$", "", str(action_row.get("reason_summary") or ""), flags=re.IGNORECASE).strip()

    db.add(
        TimelineEvent(
            intervention_id=intervention.id,
            student_id=student.id,
            event_type="AI Copilot Alert",
            description=clean_reason,
        )
    )


async def _run_pipeline(db: Session, run_by: User, run_type: str = "weekly") -> CopilotRun:
    state: Dict[str, Any] = {
        "run_type": run_type,
        "students": [],
        "predictions": [],
        "explained": [],
        "actions": [],
        "final_actions": [],
    }

    def fetch_student_data_node(s: Dict[str, Any]) -> Dict[str, Any]:
        s["students"] = _fetch_student_data(db)
        return s

    def predict_risk_node(s: Dict[str, Any]) -> Dict[str, Any]:
        s["predictions"] = _predict_risk_payload(s["students"])
        return s

    def explain_factors_node(s: Dict[str, Any]) -> Dict[str, Any]:
        s["explained"] = _explain_rows(db, s["predictions"])
        return s

    def choose_intervention_node(s: Dict[str, Any]) -> Dict[str, Any]:
        s["actions"] = _choose_actions(s["explained"], threshold=70)
        return s

    def agent_reasoning_node(s: Dict[str, Any]) -> Dict[str, Any]:
        s["final_actions"] = _agentic_reasoning(s["actions"])
        return s

    if StateGraph and START and END:
        graph = StateGraph(dict)
        graph.add_node("fetch_student_data", fetch_student_data_node)
        graph.add_node("predict_risk", predict_risk_node)
        graph.add_node("explain_factors", explain_factors_node)
        graph.add_node("choose_intervention", choose_intervention_node)
        graph.add_node("agent_reasoning", agent_reasoning_node)

        graph.add_edge(START, "fetch_student_data")
        graph.add_edge("fetch_student_data", "predict_risk")
        graph.add_edge("predict_risk", "explain_factors")
        graph.add_edge("explain_factors", "choose_intervention")
        graph.add_edge("choose_intervention", "agent_reasoning")
        graph.add_edge("agent_reasoning", END)

        compiled = graph.compile()
        state = compiled.invoke(state)
    else:
        state = fetch_student_data_node(state)
        state = predict_risk_node(state)
        state = explain_factors_node(state)
        state = choose_intervention_node(state)
        state = agent_reasoning_node(state)

    if not state["final_actions"]:
        state["final_actions"] = state["actions"]

    llm_enabled = bool(settings.ANTHROPIC_API_KEY and Anthropic is not None)

    run = CopilotRun(
        run_type=run_type,
        status="completed",
        total_students_scanned=len(state["students"]),
        high_risk_identified=len(state["final_actions"]),
        actions_created=len(state["final_actions"]),
        summary={
            "langgraph_used": bool(StateGraph),
            "execution_mode": "agentic_local",
            "agent_mode": "llm_rag" if llm_enabled else "heuristic_rag",
            "llm_model": AGENT_LLM_MODEL if llm_enabled else "none",
            "rag_backend": "policy_playbook",
            "vector_backend": "tfidf_cosine",
            "knowledge_chunks": len(COPILOT_PLAYBOOK),
        },
        created_by=run_by.name,
    )
    db.add(run)
    db.flush()

    for row in state["final_actions"]:
        student: Student = row["student"]
        ticket = CopilotActionTicket(
            run_id=run.id,
            student_id=student.id,
            student_name=student.name,
            class_name=student.class_name,
            risk_score=row["risk_score"],
            risk_trend=row.get("risk_trend") or student.risk_trend,
            reason_summary=row["reason_summary"],
            recommended_intervention=row["recommended_intervention"],
            priority=row["priority"],
            n8n_status="local_only",
            n8n_reference=None,
            status="Open",
        )
        db.add(ticket)
        _ensure_intervention_and_timeline(db, row, run_by.name, run_by.id)

    db.commit()
    db.refresh(run)

    return run


async def run_weekly_copilot(db: Session, run_by: User, run_type: str = "weekly") -> CopilotRun:
    return await _run_pipeline(db, run_by=run_by, run_type=run_type)


def list_copilot_runs(db: Session, limit: int = 20) -> List[CopilotRun]:
    return db.query(CopilotRun).order_by(CopilotRun.id.desc()).limit(limit).all()


def get_copilot_run_detail(db: Session, run_id: int) -> Dict[str, Any]:
    run = db.query(CopilotRun).filter(CopilotRun.id == run_id).first()
    if not run:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Copilot run not found")

    tickets = (
        db.query(CopilotActionTicket)
        .filter(CopilotActionTicket.run_id == run_id)
        .order_by(CopilotActionTicket.risk_score.desc())
        .all()
    )
    return {"run": run, "tickets": tickets}
