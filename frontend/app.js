/* ==========================================
   EduGuard AI - Application Logic
   ========================================== */

// ===== MOCK DATA (Replaced by API) =====

let highRiskStudents = [];
let interventions = [];
let analyticsData = null;
let selectedInterventionStudentId = null;
let userManagementAccounts = [];
let financialCases = [];
let selectedFinancialCaseId = null;
let counselingSessions = [];
let selectedCounselingStudentId = null;
let studentFinancialCase = null;
let studentAttendanceChart = null;
let studentMarksChart = null;
let copilotRuns = [];
let copilotTickets = [];
let selectedCopilotRunId = null;

function getAuthHeaders(extra = {}) {
  const user = getCurrentUser();
  const token = localStorage.getItem("eduguard_token") || user?.token;
  return token ? { Authorization: `Bearer ${token}`, ...extra } : { ...extra };
}

// ===== API FETCHING =====

async function fetchAPI(endpoint, options = {}) {
  const user = getCurrentUser();
  const headers = getAuthHeaders(options.headers || {});
  if (options.body && !(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`http://127.0.0.1:8000${endpoint}`, { ...options, headers });
  if (!res.ok) {
    if (res.status === 401) {
      if (!user || user.source !== "mock") {
        localStorage.removeItem("eduguard_user");
        localStorage.removeItem("eduguard_token");
        window.location.href = "login.html";
      }
    }
    throw new Error(`API error ${res.status}`);
  }
  return res.json();
}

async function fetchDashboardData(user) {
  if (user.role === 'admin' || user.role === 'counselor') {
    try {
      const stats = await fetchAPI('/api/analytics/dashboard');
      const statHighRisk = document.getElementById("statHighRisk");
      const statNewHighRisk = document.getElementById("statNewHighRisk");
      const statActiveInterventions = document.getElementById("statActiveInterventions");
      const statImproved = document.getElementById("statImproved");
      const navDashboardBadge = document.getElementById("navDashboardBadge");

      if (statHighRisk) statHighRisk.textContent = stats.total_high_risk;
      if (statNewHighRisk) statNewHighRisk.textContent = stats.new_high_risk_this_week;
      if (statActiveInterventions) statActiveInterventions.textContent = stats.active_interventions;
      if (statImproved) statImproved.textContent = stats.improved_after_intervention;
      if (navDashboardBadge) navDashboardBadge.textContent = stats.total_high_risk;
    } catch (e) {
      console.error("Failed to fetch dashboard stats", e);
    }
  }

  try {
    const rawStudents = await fetchAPI('/api/students/high-risk');
    highRiskStudents = rawStudents.map(s => ({
      id: s.id,
      name: s.name,
      class: s.class_name,
      semester: s.semester,
      riskScore: s.risk_score,
      trend: s.risk_trend || "up",
      attendance: s.attendance || 0,
      marks: s.marks || 0,
      factors: s.risk_factors || [],
      intervention: "None",
      counselor: null
    }));
  } catch (e) {
    console.error("Failed to fetch high risk students", e);
    highRiskStudents = [];
  }

  try {
    const rawInterventions = await fetchAPI('/api/interventions/');
    interventions = rawInterventions.map(i => ({
      studentId: i.student_id,
      studentName: i.student_name || i.student_id,
      type: i.type,
      assignedBy: i.assigned_by,
      date: i.date_assigned ? new Date(i.date_assigned).toISOString().split('T')[0] : "N/A",
      status: i.status,
      outcome: i.outcome || "—"
    }));

    // Attach intervention statuses to highRiskStudents
    highRiskStudents.forEach(s => {
      const activeIvs = interventions.filter(iv => iv.studentId === s.id);
      if (activeIvs.length > 0) {
        const active = activeIvs.find(iv => iv.status === "Active");
        const pending = activeIvs.find(iv => iv.status === "Pending");
        s.intervention = active ? "Active" : (pending ? "Pending" : "Completed");
      } else {
        s.intervention = "None";
      }
    });
  } catch (e) {
    console.error("Failed to fetch interventions", e);
    interventions = [];
  }

  updateInterventionStats();

  if (user.role === 'admin') {
    try {
      analyticsData = await fetchAPI('/api/analytics/');
    } catch (e) {
      console.error("Failed to fetch analytics data", e);
      analyticsData = null;
    }

    try {
      await loadFinancialCases();
    } catch (e) {
      console.error("Failed to load financial cases", e);
    }
  }
}

function updateInterventionStats() {
  const totalEl = document.getElementById("statInterventionsTotal");
  const pendingEl = document.getElementById("statInterventionsPending");
  const activeEl = document.getElementById("statInterventionsActive");
  const completedEl = document.getElementById("statInterventionsCompleted");

  if (!totalEl && !pendingEl && !activeEl && !completedEl) return;

  const total = interventions.length;
  const pending = interventions.filter(i => i.status === "Pending").length;
  const active = interventions.filter(i => i.status === "Active").length;
  const completed = interventions.filter(i => i.status === "Completed").length;

  if (totalEl) totalEl.textContent = total;
  if (pendingEl) pendingEl.textContent = pending;
  if (activeEl) activeEl.textContent = active;
  if (completedEl) completedEl.textContent = completed;
}

// ===== FACTOR HELPERS =====

const factorMeta = {
  financial: { icon: "fas fa-rupee-sign", label: "Financial", cls: "financial" },
  attendance: { icon: "fas fa-calendar-times", label: "Attendance", cls: "attendance" },
  academic: { icon: "fas fa-book-open", label: "Academic", cls: "academic" },
  family: { icon: "fas fa-users", label: "Family", cls: "family" },
};

function renderFactors(factors) {
  return factors.map(f => {
    const m = factorMeta[f];
    return `<div class="risk-factor-icon ${m.cls}" title="${m.label}"><i class="${m.icon}"></i><span class="tooltip">${m.label}</span></div>`;
  }).join("");
}

function getInitials(name) {
  return name.split(" ").map(w => w[0]).join("").toUpperCase();
}

// ===== RENDER TABLES =====

function renderAdminTable() {
  const tbody = document.getElementById("adminTableBody");
  if (!highRiskStudents.length) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" class="text-muted" style="text-align:center;padding:24px;">
          No high-risk students available.
        </td>
      </tr>
    `;
    return;
  }
  tbody.innerHTML = highRiskStudents.slice(0, 10).map(s => `
    <tr>
      <td>
        <div class="student-info">
          <div class="student-avatar">${getInitials(s.name)}</div>
          <div>
            <div class="student-name">${s.name}</div>
          </div>
        </div>
      </td>
      <td><span class="text-muted">${s.id}</span></td>
      <td>${s.class}</td>
      <td>
        <span class="risk-score">
          ${s.riskScore}
          <span class="risk-bar"><span class="risk-bar-fill" style="width:${s.riskScore}%"></span></span>
        </span>
      </td>
      <td>
        <span class="risk-trend ${s.trend}">
          <i class="fas fa-arrow-${s.trend}"></i> ${s.trend === "up" ? "Rising" : "Falling"}
        </span>
      </td>
      <td>
        <div class="risk-factors">${renderFactors(s.factors)}</div>
      </td>
      <td>
        <div class="flex items-center" style="gap:6px;">
          <button class="btn btn-ghost btn-sm" onclick="openTimelineModal('${s.id}', '${s.name.replace(/'/g, "\\'")}')"><i class="fas fa-eye"></i> View</button>
          <button class="btn btn-outline btn-sm" onclick="openRiskTrendModal('${s.id}', '${s.name.replace(/'/g, "\\'")}')"><i class="fas fa-chart-line"></i> Trend</button>
          <button class="btn btn-danger btn-sm" onclick="openInterventionModal('${s.id}')"><i class="fas fa-plus"></i> Intervene</button>
        </div>
      </td>
    </tr>
  `).join("");
}

function renderHighRiskTable() {
  const tbody = document.getElementById("highRiskTableBody");
  const user = getCurrentUser();
  const isCounselor = user?.role === "counselor";

  if (!highRiskStudents.length) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" class="text-muted" style="text-align:center;padding:24px;">
          No high-risk students found for selected filters.
        </td>
      </tr>
    `;
    return;
  }
  tbody.innerHTML = highRiskStudents.map(s => `
    <tr>
      <td>
        <div class="student-info">
          <div class="student-avatar">${getInitials(s.name)}</div>
          <div>
            <div class="student-name">${s.name}</div>
            <div class="student-id-text">${s.id}</div>
          </div>
        </div>
      </td>
      <td>${s.class}</td>
      <td>
        <span class="risk-score">
          ${s.riskScore}
          <span class="risk-bar"><span class="risk-bar-fill" style="width:${s.riskScore}%"></span></span>
        </span>
      </td>
      <td>
        <div class="risk-factors">${renderFactors(s.factors)}</div>
      </td>
      <td>
        ${(() => {
          if (isCounselor) {
            const counseling = getCounselingStatusForStudent(s.id);
            return `<span class="badge badge-${counseling.cls}">${counseling.label}</span>`;
          }
          return `<span class="badge badge-${s.intervention === 'Active' ? 'active' : s.intervention === 'Pending' ? 'pending' : 'danger'}">${s.intervention === 'None' ? '⚠ None' : s.intervention}</span>`;
        })()}
      </td>
      <td>
        ${isCounselor
          ? `<button class="btn btn-ghost btn-sm" onclick="openTimelineModal('${s.id}', '${s.name.replace(/'/g, "\\'")}')"><i class="fas fa-history"></i> Timeline</button>`
          : `<button class="btn btn-primary btn-sm" onclick="openInterventionModal('${s.id}')"><i class="fas fa-hand-holding-heart"></i> Assign</button>`}
      </td>
    </tr>
  `).join("");
}

function renderInterventionsTable() {
  const tbody = document.getElementById("interventionsTableBody");
  if (!interventions.length) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" class="text-muted" style="text-align:center;padding:24px;">
          No interventions available.
        </td>
      </tr>
    `;
    return;
  }
  tbody.innerHTML = interventions.map(i => `
    <tr>
      <td>
        <div class="student-info">
          <div class="student-avatar">${getInitials(i.studentName)}</div>
          <div class="student-name">${i.studentName}</div>
        </div>
      </td>
      <td>${i.type}</td>
      <td>${i.assignedBy}</td>
      <td>${i.date}</td>
      <td><span class="badge badge-${i.status.toLowerCase()}">${i.status}</span></td>
      <td>
        <span class="${i.outcome === 'Improving' || i.outcome === 'Improved' ? 'text-cyan' : i.outcome === 'Stable' ? 'text-blue' : 'text-muted'}">${i.outcome}</span>
      </td>
      <td>
        <button class="btn btn-ghost btn-sm" onclick="openTimelineModal('${i.studentId}', '${i.studentName.replace(/'/g, "\\'")}')"><i class="fas fa-history"></i> Timeline</button>
      </td>
    </tr>
  `).join("");
}

async function applyHighRiskFilters() {
  const classFilter = document.getElementById("filterClass")?.value?.trim();
  const semesterFilter = document.getElementById("filterSemester")?.value?.trim();
  const causeFilter = document.getElementById("filterCause")?.value?.trim();

  const params = new URLSearchParams();
  if (classFilter) params.set("class", classFilter);
  if (semesterFilter) params.set("semester", semesterFilter);
  if (causeFilter) params.set("factor", causeFilter.toLowerCase());

  try {
    const query = params.toString();
    const rawStudents = await fetchAPI(`/api/students/high-risk${query ? `?${query}` : ""}`);
    highRiskStudents = (rawStudents || []).map(s => ({
      id: s.id,
      name: s.name,
      class: s.class_name,
      semester: s.semester,
      riskScore: s.risk_score,
      trend: s.risk_trend || "up",
      attendance: s.attendance || 0,
      marks: s.marks || 0,
      factors: s.risk_factors || [],
      intervention: "None",
      counselor: null
    }));

    highRiskStudents.forEach(s => {
      const activeIvs = interventions.filter(iv => iv.studentId === s.id);
      if (activeIvs.length > 0) {
        const active = activeIvs.find(iv => iv.status === "Active");
        const pending = activeIvs.find(iv => iv.status === "Pending");
        s.intervention = active ? "Active" : (pending ? "Pending" : "Completed");
      }
    });

    renderHighRiskTable();
    renderAdminTable();
  } catch (e) {
    alert("Failed to apply filters.");
  }
}

function exportHighRiskCsv() {
  if (!highRiskStudents.length) {
    alert("No high-risk students to export.");
    return;
  }

  const header = ["Student ID", "Name", "Class", "Semester", "Risk Score", "Trend", "Risk Factors", "Intervention"];
  const rows = highRiskStudents.map(s => [
    s.id,
    s.name,
    s.class,
    s.semester,
    s.riskScore,
    s.trend,
    (s.factors || []).join("|"),
    s.intervention,
  ]);

  const csv = [header, ...rows]
    .map(cols => cols.map(v => `"${String(v ?? "").replace(/"/g, '""')}"`).join(","))
    .join("\n");

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `high_risk_students_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

async function downloadReport(kind) {
  const routeMap = {
    "high-risk-summary": "/api/reports/high-risk-summary",
    interventions: "/api/reports/interventions",
    analytics: "/api/reports/analytics",
    "monthly-trend": "/api/reports/monthly-trend",
  };

  const endpoint = routeMap[kind];
  if (!endpoint) return;

  try {
    const res = await fetch(`http://127.0.0.1:8000${endpoint}`, {
      method: "GET",
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error(`Report error ${res.status}`);

    const blob = await res.blob();
    const disp = res.headers.get("content-disposition") || "";
    const match = disp.match(/filename=([^;]+)/i);
    const filename = match ? match[1].replace(/"/g, "") : `report_${Date.now()}`;

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  } catch (e) {
    alert("Failed to download report.");
  }
}

async function loadSettings() {
  try {
    const settings = await fetchAPI('/api/settings/');
    if (!settings) return;

    const highRisk = document.getElementById("highRiskThreshold");
    const attendance = document.getElementById("attendanceThreshold");
    const marksDrop = document.getElementById("marksDropThreshold");
    const email = document.getElementById("emailNotifications");
    const sms = document.getElementById("smsAlerts");
    const ai = document.getElementById("aiSuggestions");

    if (highRisk) highRisk.value = settings.high_risk_threshold;
    if (attendance) attendance.value = settings.attendance_alert_threshold;
    if (marksDrop) marksDrop.value = settings.marks_drop_alert_percentage;
    if (email) email.value = settings.email_notifications ? "Enabled" : "Disabled";
    if (sms) sms.value = settings.sms_alerts ? "Enabled" : "Disabled";
    if (ai) ai.value = settings.ai_auto_suggestions ? "Enabled" : "Disabled";
  } catch (e) {
    console.error("Failed to load settings", e);
  }
}

async function saveThresholds() {
  const payload = {
    high_risk_threshold: Number(document.getElementById("highRiskThreshold")?.value || 70),
    attendance_alert_threshold: Number(document.getElementById("attendanceThreshold")?.value || 60),
    marks_drop_alert_percentage: Number(document.getElementById("marksDropThreshold")?.value || 20),
  };

  try {
    await fetchAPI('/api/settings/thresholds', {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
    alert("Thresholds saved.");
  } catch (e) {
    alert("Failed to save thresholds.");
  }
}

async function savePreferences() {
  const payload = {
    email_notifications: (document.getElementById("emailNotifications")?.value || "Enabled") === "Enabled",
    sms_alerts: (document.getElementById("smsAlerts")?.value || "Enabled") === "Enabled",
    ai_auto_suggestions: (document.getElementById("aiSuggestions")?.value || "Enabled") === "Enabled",
  };

  try {
    await fetchAPI('/api/settings/notifications', {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
    alert("Preferences saved.");
  } catch (e) {
    alert("Failed to save preferences.");
  }
}

async function loadFinancialCases() {
  const user = getCurrentUser();
  if (!user || user.role !== 'admin') return;

  try {
    financialCases = await fetchAPI('/api/financial-support/cases');
  } catch (e) {
    financialCases = [];
    throw e;
  }

  renderFinancialCasesTable();
}

function renderFinancialCasesTable() {
  const tbody = document.getElementById('financialCasesTableBody');
  if (!tbody) return;

  if (!financialCases.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-muted" style="text-align:center;padding:16px;">No financial support cases yet.</td></tr>';
    return;
  }

  tbody.innerHTML = financialCases.map(c => {
    const aiTips = (c.ai_recommendations || []).slice(0, 2).map(t => `• ${escapeHtml(t)}`).join('<br/>') || '<span class="text-muted">Awaiting AI suggestions</span>';
    const feeText = c.fee_outstanding_amount !== null && c.fee_outstanding_amount !== undefined
      ? `₹${Number(c.fee_outstanding_amount).toLocaleString()}`
      : '—';
    return `
      <tr>
        <td>
          <div class="student-info">
            <div class="student-avatar">${getInitials(c.student_name || c.student_id || 'NA')}</div>
            <div>
              <div class="student-name">${escapeHtml(c.student_name || c.student_id || 'Unknown')}</div>
              <div class="student-id-text">${escapeHtml(c.student_id || '—')}</div>
            </div>
          </div>
        </td>
        <td><span class="badge badge-blue">${escapeHtml(c.status || 'Pending')}</span></td>
        <td>${feeText}</td>
        <td>${escapeHtml(c.preferred_support_type || '—')}</td>
        <td style="font-size:12px;line-height:1.5;max-width:320px;">${aiTips}</td>
        <td>
          <button class="btn btn-primary btn-sm" onclick="openFinancialPlanModal(${c.id})"><i class="fas fa-lightbulb"></i> Plan</button>
        </td>
      </tr>
    `;
  }).join('');
}

function openFinancialPlanModal(caseId) {
  const current = financialCases.find(c => Number(c.id) === Number(caseId));
  selectedFinancialCaseId = caseId;

  const title = document.getElementById('financialPlanTitle');
  const planType = document.getElementById('financialPlanType');
  const planText = document.getElementById('financialPlanText');
  const notes = document.getElementById('financialPlanNotes');

  if (title) title.textContent = `Publish Financial Support Plan — ${current?.student_name || current?.student_id || 'Student'}`;
  if (planType) planType.value = current?.admin_plan_type || '';
  if (planText) planText.value = current?.admin_plan || '';
  if (notes) notes.value = current?.admin_notes || '';

  openModal('financialPlanModal');
}

async function saveFinancialPlan() {
  if (!selectedFinancialCaseId) return;

  const planType = document.getElementById('financialPlanType')?.value?.trim() || null;
  const planText = document.getElementById('financialPlanText')?.value?.trim() || null;
  const notes = document.getElementById('financialPlanNotes')?.value?.trim() || null;

  if (!planText) {
    alert('Please enter plan details.');
    return;
  }

  try {
    await fetchAPI(`/api/financial-support/cases/${selectedFinancialCaseId}/plan`, {
      method: 'PUT',
      body: JSON.stringify({
        admin_plan_type: planType,
        admin_plan: planText,
        admin_notes: notes,
        status: 'Plan Shared',
      }),
    });

    closeModal('financialPlanModal');
    await loadFinancialCases();
    alert('Financial support plan published.');
  } catch (e) {
    alert('Failed to publish financial support plan.');
  }
}

async function loadStudentFinancialSupportCase() {
  const user = getCurrentUser();
  if (!user || user.role !== 'student') return;

  const hubCard = document.getElementById('studentFinancialHubCard');
  const planText = document.getElementById('studentFinancialPlanText');
  const aiTips = document.getElementById('studentFinancialAiTips');
  if (!hubCard) return;

  try {
    const c = await fetchAPI('/api/financial-support/my-case');
    studentFinancialCase = c;
    hubCard.style.display = '';

    document.getElementById('studentFeeOutstandingAmount').value = c.fee_outstanding_amount ?? '';
    document.getElementById('studentScholarshipEligibility').value = c.scholarship_eligibility ?? '';
    document.getElementById('studentSocialCategory').value = c.social_category ?? '';
    document.getElementById('studentParentOccupation').value = c.parent_occupation ?? '';
    document.getElementById('studentIncomeBand').value = c.family_income_band ?? '';
    document.getElementById('studentScholarshipApplied').value = c.scholarship_applied ?? '';
    document.getElementById('studentPreferredSupportType').value = c.preferred_support_type ?? '';
    document.getElementById('studentFinancialNotes').value = c.student_notes ?? '';

    if (planText) {
      planText.textContent = c.admin_plan
        ? `Plan (${c.admin_plan_type || 'Support'}): ${c.admin_plan}`
        : 'Support plan will appear here once admin reviews your details.';
    }
    if (aiTips) {
      aiTips.innerHTML = (c.ai_recommendations || []).length
        ? `<strong>AI Suggestions:</strong><br/>${c.ai_recommendations.map(t => `• ${escapeHtml(t)}`).join('<br/>')}`
        : '';
    }
    await refreshStudentDashboardEnhancements();
  } catch (e) {
    studentFinancialCase = null;
    hubCard.style.display = 'none';
    await refreshStudentDashboardEnhancements();
  }
}

async function submitStudentFinancialInput() {
  const payload = {
    fee_outstanding_amount: Number(document.getElementById('studentFeeOutstandingAmount')?.value || 0) || null,
    scholarship_eligibility: document.getElementById('studentScholarshipEligibility')?.value || null,
    social_category: document.getElementById('studentSocialCategory')?.value || null,
    parent_occupation: document.getElementById('studentParentOccupation')?.value?.trim() || null,
    family_income_band: document.getElementById('studentIncomeBand')?.value || null,
    scholarship_applied: document.getElementById('studentScholarshipApplied')?.value || null,
    preferred_support_type: document.getElementById('studentPreferredSupportType')?.value || null,
    student_notes: document.getElementById('studentFinancialNotes')?.value?.trim() || null,
  };

  try {
    await fetchAPI('/api/financial-support/my-case/input', {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
    await loadStudentFinancialSupportCase();
    alert('Financial support details submitted successfully.');
  } catch (e) {
    alert('Failed to submit details. Please contact admin if this persists.');
  }
}

async function loadCopilotRuns() {
  const user = getCurrentUser();
  if (!user || user.role !== "admin") return;

  try {
    const rows = await fetchAPI('/api/copilot/runs?limit=20');
    copilotRuns = Array.isArray(rows) ? rows : [];
    renderCopilotRunsTable();

    if (copilotRuns.length) {
      await openCopilotRun(copilotRuns[0].id, false);
    } else {
      copilotTickets = [];
      renderCopilotTicketsTable();
    }
  } catch (e) {
    copilotRuns = [];
    copilotTickets = [];
    renderCopilotRunsTable();
    renderCopilotTicketsTable();
  }
}

function renderCopilotRunsTable() {
  const tbody = document.getElementById("copilotRunsTableBody");
  const runsEl = document.getElementById("copilotStatRuns");
  const lastRunEl = document.getElementById("copilotStatLastRun");
  const actionsEl = document.getElementById("copilotStatActions");
  const criticalEl = document.getElementById("copilotStatCritical");

  if (runsEl) runsEl.textContent = copilotRuns.length;
  if (actionsEl) actionsEl.textContent = copilotRuns.reduce((acc, run) => acc + Number(run.actions_created || 0), 0);
  if (criticalEl) {
    const critical = copilotTickets.filter(t => String(t.priority || "").toLowerCase() === "critical").length;
    criticalEl.textContent = critical;
  }
  if (lastRunEl) {
    lastRunEl.textContent = copilotRuns[0]?.created_at
      ? new Date(copilotRuns[0].created_at).toLocaleDateString()
      : "—";
  }

  if (!tbody) return;

  if (!copilotRuns.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-muted" style="text-align:center;padding:16px;">No Copilot runs yet.</td></tr>';
    return;
  }

  tbody.innerHTML = copilotRuns.map(run => {
    const createdAt = run.created_at ? new Date(run.created_at).toLocaleString() : "—";
    const status = String(run.status || "completed").toLowerCase();
    const badge = status === "completed" ? "completed" : status === "running" ? "active" : "pending";
    const isSelected = Number(selectedCopilotRunId) === Number(run.id);
    return `
      <tr style="${isSelected ? 'background:rgba(37,99,235,0.10);' : ''}">
        <td>#${run.id}</td>
        <td>${escapeHtml(run.run_type || "weekly")}</td>
        <td>${run.total_students_scanned || 0}</td>
        <td>${run.high_risk_identified || 0}</td>
        <td>${run.actions_created || 0}</td>
        <td><span class="badge badge-${badge}">${escapeHtml(run.status || "completed")}</span></td>
        <td>
          <button class="btn btn-ghost btn-sm" onclick="openCopilotRun(${run.id}, true)"><i class="fas fa-eye"></i> View</button>
          <span class="text-muted" style="margin-left:8px;font-size:12px;">${createdAt}</span>
        </td>
      </tr>
    `;
  }).join("");
}

function renderCopilotTicketsTable() {
  const tbody = document.getElementById("copilotTicketsTableBody");
  const criticalEl = document.getElementById("copilotStatCritical");
  if (!tbody) return;

  if (!copilotTickets.length) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-muted" style="text-align:center;padding:16px;">No action tickets yet.</td></tr>';
    if (criticalEl) criticalEl.textContent = "0";
    return;
  }

  const critical = copilotTickets.filter(t => String(t.priority || "").toLowerCase() === "critical").length;
  if (criticalEl) criticalEl.textContent = critical;

  tbody.innerHTML = copilotTickets.map(t => {
    const risk = Number(t.risk_score || 0);
    const priorityCls = String(t.priority || "").toLowerCase() === "critical"
      ? "danger"
      : String(t.priority || "").toLowerCase() === "high" ? "pending" : "active";
    const cleanReason = String(t.reason_summary || "—").replace(/\s*\[RAG:[\s\S]*?\]\s*$/i, "").trim() || "—";
    return `
      <tr>
        <td>${escapeHtml(t.student_name || t.student_id || "—")}</td>
        <td><span class="text-muted">${escapeHtml(t.student_id || "—")}</span></td>
        <td>${escapeHtml(t.class_name || "—")}</td>
        <td>${risk.toFixed(1)}</td>
        <td><span class="badge badge-${priorityCls}">${escapeHtml(t.priority || "Medium")}</span></td>
        <td>${escapeHtml(t.recommended_intervention || "—")}</td>
        <td style="max-width:320px;">${escapeHtml(cleanReason)}</td>
        <td>${escapeHtml(t.status || "Open")}</td>
      </tr>
    `;
  }).join("");
}

async function openCopilotRun(runId, notify = false) {
  try {
    selectedCopilotRunId = Number(runId);
    const detail = await fetchAPI(`/api/copilot/runs/${runId}`);
    copilotTickets = Array.isArray(detail?.tickets) ? detail.tickets : [];
    renderCopilotRunsTable();
    renderCopilotTicketsTable();

    const lastRunEl = document.getElementById("copilotStatLastRun");
    if (lastRunEl && detail?.run?.created_at) {
      lastRunEl.textContent = new Date(detail.run.created_at).toLocaleDateString();
    }

    const ticketsTitleEl = document.getElementById("copilotTicketsTitle");
    if (ticketsTitleEl) {
      const createdAt = detail?.run?.created_at
        ? new Date(detail.run.created_at).toLocaleString()
        : "—";
      ticketsTitleEl.textContent = `Action Tickets — Run #${runId} (${createdAt})`;
    }

    if (notify) {
      document.getElementById("copilotTicketsTableBody")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  } catch (e) {
    selectedCopilotRunId = null;
    copilotTickets = [];
    renderCopilotRunsTable();
    renderCopilotTicketsTable();
    const ticketsTitleEl = document.getElementById("copilotTicketsTitle");
    if (ticketsTitleEl) ticketsTitleEl.textContent = "Action Tickets";
    alert(`Failed to load Copilot run #${runId}. Please refresh and try again.`);
  }
}

async function runWeeklyCopilot() {
  const btn = document.getElementById("runCopilotBtn");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> Running...';
  }

  try {
    const run = await fetchAPI('/api/copilot/runs', {
      method: 'POST',
      body: JSON.stringify({ run_type: 'weekly' }),
    });

    await loadCopilotRuns();
    await openCopilotRun(run.id, false);
    alert(`Copilot run #${run.id} completed. Action tickets generated: ${run.actions_created}.`);
  } catch (e) {
    alert("Copilot run failed. Please check backend logs.");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-play"></i> Run Weekly Copilot';
    }
  }
}

async function loadUserManagementData() {
  try {
    const users = await fetchAPI('/api/users/');
    userManagementAccounts = Array.isArray(users) ? users : [];
    renderUserManagementTable();
  } catch (e) {
    alert("Failed to load faculty/counselor accounts.");
  }
}

function renderUserManagementTable() {
  const tbody = document.getElementById("userManagementTableBody");
  if (!tbody) return;

  if (!userManagementAccounts.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-muted" style="text-align:center;padding:16px;">No faculty/counselor accounts found.</td></tr>';
    return;
  }

  tbody.innerHTML = userManagementAccounts.map(user => {
    const role = user.role === "faculty" ? "Faculty" : "Counselor";
    const roleBadge = user.role === "faculty"
      ? '<span class="badge badge-blue">Faculty</span>'
      : '<span class="badge badge-cyan">Counselor</span>';
    const classInputId = `facultyClassInput_${user.id}`;

    return `
      <tr>
        <td>${escapeHtml(user.name || "—")}</td>
        <td><span class="text-muted">${escapeHtml(user.id || "—")}</span></td>
        <td>${escapeHtml(user.email || "—")}</td>
        <td>${roleBadge}</td>
        <td>
          ${user.role === "faculty"
            ? `<input type="text" id="${classInputId}" value="${escapeHtml(user.assigned_class || "")}" placeholder="CS-A" style="max-width:120px;" />`
            : '<span class="text-muted">Not Applicable</span>'}
        </td>
        <td>
          ${user.role === "faculty"
            ? `<button class="btn btn-primary btn-sm" onclick="updateFacultyClass('${user.id}')"><i class="fas fa-save"></i> Save Class</button>`
            : `<span class="text-muted">${role}</span>`}
        </td>
      </tr>
    `;
  }).join("");
}

async function createFacultyAccount() {
  const name = document.getElementById("facultyCreateName")?.value?.trim();
  const email = document.getElementById("facultyCreateEmail")?.value?.trim();
  const password = document.getElementById("facultyCreatePassword")?.value?.trim();
  const assignedClass = document.getElementById("facultyCreateClass")?.value?.trim();

  if (!name || !email || !password || !assignedClass) {
    alert("Please fill all faculty fields.");
    return;
  }

  try {
    await fetchAPI('/api/users/', {
      method: 'POST',
      body: JSON.stringify({
        name,
        email,
        password,
        role: 'faculty',
        assigned_class: assignedClass,
      }),
    });

    document.getElementById("facultyCreateName").value = "";
    document.getElementById("facultyCreateEmail").value = "";
    document.getElementById("facultyCreatePassword").value = "";
    document.getElementById("facultyCreateClass").value = "";

    await loadUserManagementData();
    alert("Faculty account created.");
  } catch (e) {
    alert("Failed to create faculty account.");
  }
}

async function createCounselorAccount() {
  const name = document.getElementById("counselorCreateName")?.value?.trim();
  const email = document.getElementById("counselorCreateEmail")?.value?.trim();
  const password = document.getElementById("counselorCreatePassword")?.value?.trim();

  if (!name || !email || !password) {
    alert("Please fill all counselor fields.");
    return;
  }

  try {
    await fetchAPI('/api/users/', {
      method: 'POST',
      body: JSON.stringify({
        name,
        email,
        password,
        role: 'counselor',
      }),
    });

    document.getElementById("counselorCreateName").value = "";
    document.getElementById("counselorCreateEmail").value = "";
    document.getElementById("counselorCreatePassword").value = "";

    await loadUserManagementData();
    alert("Counselor account created.");
  } catch (e) {
    alert("Failed to create counselor account.");
  }
}

async function updateFacultyClass(userId) {
  const input = document.getElementById(`facultyClassInput_${userId}`);
  const assignedClass = input?.value?.trim();

  if (!assignedClass) {
    alert("Please enter a class.");
    return;
  }

  try {
    await fetchAPI(`/api/users/${userId}/class`, {
      method: 'PUT',
      body: JSON.stringify({ assigned_class: assignedClass }),
    });
    await loadUserManagementData();
    alert("Faculty class updated.");
  } catch (e) {
    alert("Failed to update faculty class.");
  }
}

function refreshAnalytics() {
  return;
}

function renderFacultyTable() {
  const tbody = document.getElementById("facultyTableBody");
  const user = getCurrentUser();
  const assignedClass = user?.assigned_class || null;
  const classStudents = assignedClass
    ? highRiskStudents.filter(s => s.class === assignedClass)
    : highRiskStudents;

  updateFacultyStats(classStudents, assignedClass);

  if (!classStudents.length) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" class="text-muted" style="text-align:center;padding:24px;">
          No high-risk students found for your assigned class.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = classStudents.map(s => `
    <tr>
      <td>
        <div class="student-info">
          <div class="student-avatar">${getInitials(s.name)}</div>
          <div>
            <div class="student-name">${s.name}</div>
            <div class="student-id-text">${s.id}</div>
          </div>
        </div>
      </td>
      <td><span class="text-danger" style="font-weight:600;">${s.attendance}%</span></td>
      <td><span class="text-danger" style="font-weight:600;">${s.marks}/100</span></td>
      <td>
        <span class="risk-score">
          ${s.riskScore}
          <span class="risk-bar"><span class="risk-bar-fill" style="width:${s.riskScore}%"></span></span>
        </span>
      </td>
      <td>
        <span class="risk-trend ${s.trend}">
          <i class="fas fa-arrow-${s.trend}"></i> ${s.trend === "up" ? "Rising" : "Falling"}
        </span>
      </td>
      <td>
        <span class="badge badge-${s.intervention === 'Active' ? 'active' : s.intervention === 'Pending' ? 'pending' : 'danger'}">${s.intervention === 'None' ? '⚠ None' : s.intervention}</span>
      </td>
      <td>
        <div class="flex items-center" style="gap:6px;">
          <button class="btn btn-ghost btn-sm" onclick="openTimelineModal('${s.id}', '${s.name.replace(/'/g, "\\'")}')"><i class="fas fa-eye"></i> View</button>
          <button class="btn btn-outline btn-sm" onclick="openRiskTrendModal('${s.id}', '${s.name.replace(/'/g, "\\'")}')"><i class="fas fa-chart-line"></i> Trend</button>
        </div>
      </td>
    </tr>
  `).join("");
}

function updateFacultyStats(classStudents, assignedClass) {
  const classNameEl = document.getElementById("facultyClassName");
  const highRiskEl = document.getElementById("facultyStatHighRisk");
  const attendanceDropEl = document.getElementById("facultyStatAttendanceDrop");
  const marksDropEl = document.getElementById("facultyStatMarksDrop");
  const immediateEl = document.getElementById("facultyStatImmediate");

  if (classNameEl) classNameEl.textContent = assignedClass || "Assigned Class";

  const highRiskCount = classStudents.length;
  const attendanceDropCount = classStudents.filter(s => Number(s.attendance || 0) < 60).length;
  const marksDropCount = classStudents.filter(s => Number(s.marks || 0) < 40).length;
  const immediateCount = classStudents.filter(s => Number(s.riskScore || 0) >= 85 && s.intervention === "None").length;

  if (highRiskEl) highRiskEl.textContent = highRiskCount;
  if (attendanceDropEl) attendanceDropEl.textContent = attendanceDropCount;
  if (marksDropEl) marksDropEl.textContent = marksDropCount;
  if (immediateEl) immediateEl.textContent = immediateCount;
}

function updateCounselorStats() {
  const requiringEl = document.getElementById("counselorStatRequiring");
  const activeSessionsEl = document.getElementById("counselorStatActiveSessions");
  const criticalEl = document.getElementById("counselorStatCritical");
  const awaitingEl = document.getElementById("counselorStatAwaiting");

  if (!requiringEl && !activeSessionsEl && !criticalEl && !awaitingEl) return;

  const requiringCounseling = highRiskStudents.length;
  const activeSessions = counselingSessions.filter(i => String(i.status || "").toLowerCase() === "active").length;
  const criticalStudents = highRiskStudents.filter(s => Number(s.riskScore || 0) >= 85).length;
  const awaitingIntervention = highRiskStudents.filter(s => s.intervention === "None").length;

  if (requiringEl) requiringEl.textContent = requiringCounseling;
  if (activeSessionsEl) activeSessionsEl.textContent = activeSessions;
  if (criticalEl) criticalEl.textContent = criticalStudents;
  if (awaitingEl) awaitingEl.textContent = awaitingIntervention;
}

function getCounselingStatusForStudent(studentId) {
  const sessions = counselingSessions
    .filter(s => s.student_id === studentId)
    .sort((a, b) => new Date(b.scheduled_at).getTime() - new Date(a.scheduled_at).getTime());

  if (!sessions.length) return { label: "Not Scheduled", cls: "pending" };

  const latest = sessions[0];
  const status = String(latest.status || "").toLowerCase();
  if (status === "completed") return { label: "Completed", cls: "completed" };
  if (status === "active") return { label: "Active", cls: "active" };
  return { label: latest.status || "Pending", cls: "pending" };
}

function renderCounselorCards() {
  const container = document.getElementById("counselorCards");
  if (!container) return;

  updateCounselorStats();

  if (!highRiskStudents.length) {
    container.innerHTML = `
      <div class="card" style="grid-column:1/-1;">
        <div class="card-body text-muted" style="text-align:center;">No high-risk student profiles available.</div>
      </div>
    `;
    return;
  }

  container.innerHTML = highRiskStudents.slice(0, 8).map(s => {
    const counseling = getCounselingStatusForStudent(s.id);
    return `
    <div class="risk-card">
      <div class="glow-overlay"></div>
      <div class="risk-card-header">
        <div class="student-info-col">
          <h4>${s.name}</h4>
          <span>${s.id} · ${s.class}</span>
        </div>
        <div class="risk-score-large">${s.riskScore}</div>
      </div>
      <div class="risk-factors-row">${renderFactors(s.factors)}</div>
      <div class="risk-detail">
        <span><i class="fas fa-calendar-alt"></i></span> Last update: ${getCounselorStudentLastUpdate(s.id)}
      </div>
      <div class="risk-detail">
        <span><i class="fas fa-comments"></i></span> Counseling: <span class="badge badge-${counseling.cls}" style="margin-left:4px;">${counseling.label}</span>
      </div>
      <div class="risk-detail">
        <span><i class="fas fa-clipboard-check"></i></span> Other Interventions: <span class="badge badge-${s.intervention === 'Active' ? 'active' : s.intervention === 'Pending' ? 'pending' : 'danger'}" style="margin-left:4px;">${s.intervention === 'None' ? '⚠ None' : s.intervention}</span>
      </div>
      <div class="risk-card-actions">
        <button class="btn btn-ghost btn-sm" onclick="openTimelineModal('${s.id}', '${s.name.replace(/'/g, "\\'")}')"><i class="fas fa-history"></i> Timeline</button>
        <button class="btn btn-outline btn-sm" onclick="openRiskTrendModal('${s.id}', '${s.name.replace(/'/g, "\\'")}')"><i class="fas fa-chart-line"></i> Trend</button>
      </div>
    </div>
  `;
  }).join("");
}

async function loadCounselingSessions() {
  const user = getCurrentUser();
  if (!user || !["admin", "counselor", "faculty", "student"].includes(user.role)) {
    counselingSessions = [];
    return;
  }

  try {
    const rows = await fetchAPI('/api/counseling/sessions/me');
    counselingSessions = Array.isArray(rows) ? rows : [];
  } catch (e) {
    counselingSessions = [];
  }

  renderCounselingManagementTable();
  renderFacultyCounselingMessages();
  renderStudentCounselingMessages();
  updateCounselorStats();
}

function openCounselingScheduleModal(studentId, studentName, className) {
  selectedCounselingStudentId = studentId;

  const title = document.getElementById("counselingScheduleTitle");
  const whenEl = document.getElementById("counselingScheduleAt");
  const studentMsgEl = document.getElementById("counselingMessageStudent");
  const facultyMsgEl = document.getElementById("counselingMessageFaculty");
  const notesEl = document.getElementById("counselingScheduleNotes");

  if (title) title.textContent = `Schedule Counseling Session — ${studentName} (${className})`;
  if (whenEl) {
    const dt = new Date(Date.now() + 60 * 60 * 1000);
    const local = new Date(dt.getTime() - (dt.getTimezoneOffset() * 60000)).toISOString().slice(0, 16);
    whenEl.value = local;
  }
  if (studentMsgEl) studentMsgEl.value = "We are scheduling a counseling support session to help you stay on track.";
  if (facultyMsgEl) facultyMsgEl.value = `Counseling scheduled for ${studentName}. Please coordinate attendance and follow-up.`;
  if (notesEl) notesEl.value = "";

  openModal("counselingScheduleModal");
}

async function submitCounselingSchedule() {
  if (!selectedCounselingStudentId) {
    alert("Please select a student for counseling.");
    return;
  }

  const when = document.getElementById("counselingScheduleAt")?.value;
  const msgStudent = document.getElementById("counselingMessageStudent")?.value?.trim() || null;
  const msgFaculty = document.getElementById("counselingMessageFaculty")?.value?.trim() || null;
  const notes = document.getElementById("counselingScheduleNotes")?.value?.trim() || null;

  if (!when) {
    alert("Please choose session date and time.");
    return;
  }

  try {
    await fetchAPI('/api/counseling/sessions', {
      method: 'POST',
      body: JSON.stringify({
        student_id: selectedCounselingStudentId,
        scheduled_at: new Date(when).toISOString(),
        message_to_student: msgStudent,
        message_to_faculty: msgFaculty,
        notes,
      }),
    });

    closeModal('counselingScheduleModal');
    const user = getCurrentUser();
    if (user) {
      await fetchDashboardData(user);
      await loadCounselingSessions();
      renderAdminTable();
      renderHighRiskTable();
      renderInterventionsTable();
      renderFacultyTable();
      renderCounselorCards();
    }
    alert("Counseling session scheduled.");
  } catch (err) {
    alert('Failed to schedule counseling session: ' + err.message);
  }
}

function renderCounselingManagementTable() {
  const tbody = document.getElementById("counselingSessionsTableBody");
  const activeEl = document.getElementById("counselingMgmtActive");
  const completedEl = document.getElementById("counselingMgmtCompleted");

  const activeCount = counselingSessions.filter(s => String(s.status || "").toLowerCase() === "active").length;
  const completedCount = counselingSessions.filter(s => String(s.status || "").toLowerCase() === "completed").length;

  if (activeEl) activeEl.textContent = activeCount;
  if (completedEl) completedEl.textContent = completedCount;

  if (!tbody) return;

  if (!counselingSessions.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-muted" style="text-align:center;padding:16px;">No counseling sessions scheduled yet.</td></tr>';
    return;
  }

  tbody.innerHTML = counselingSessions.map(s => {
    const dt = new Date(s.scheduled_at);
    const whenText = isNaN(dt.getTime()) ? "—" : dt.toLocaleString();
    const statusLower = String(s.status || "").toLowerCase();
    const badge = statusLower === "completed" ? "completed" : "active";
    const canComplete = statusLower !== "completed";
    return `
      <tr>
        <td>${escapeHtml(s.student_name || s.student_id || "—")}</td>
        <td>${escapeHtml(s.class_name || "—")}</td>
        <td>${whenText}</td>
        <td><span class="badge badge-${badge}">${escapeHtml(s.status || "—")}</span></td>
        <td>${escapeHtml(s.message_to_student || "—")}</td>
        <td>${escapeHtml(s.message_to_faculty || "—")}</td>
        <td>
          ${canComplete
            ? `<button class="btn btn-primary btn-sm" onclick="completeCounselingSession(${s.id})"><i class="fas fa-check"></i> Complete</button>`
            : '<span class="text-muted">Completed</span>'}
        </td>
      </tr>
    `;
  }).join("");
}

async function completeCounselingSession(sessionId) {
  const notes = prompt("Completion notes (optional):", "") || "";
  try {
    await fetchAPI(`/api/counseling/sessions/${sessionId}/complete`, {
      method: 'PUT',
      body: JSON.stringify({ completion_notes: notes, outcome: 'Improved' }),
    });

    const user = getCurrentUser();
    if (user) {
      await fetchDashboardData(user);
      await loadCounselingSessions();
      renderInterventionsTable();
      renderCounselorCards();
    }
    alert('Counseling session marked as completed.');
  } catch (err) {
    alert('Failed to complete counseling session: ' + err.message);
  }
}

function renderFacultyCounselingMessages() {
  const container = document.getElementById("facultyCounselingMessages");
  if (!container) return;

  if (!counselingSessions.length) {
    container.innerHTML = '<div class="text-muted">No counseling updates yet.</div>';
    return;
  }

  container.innerHTML = counselingSessions.slice(0, 6).map(s => {
    const dt = new Date(s.scheduled_at);
    const whenText = isNaN(dt.getTime()) ? "—" : dt.toLocaleString();
    return `
      <div style="padding:10px 0;border-bottom:1px solid var(--border-color);">
        <div style="font-weight:600;">${escapeHtml(s.student_name || s.student_id || "Student")}</div>
        <div class="text-muted" style="font-size:12px;">${whenText} · ${escapeHtml(s.status || "")}</div>
        <div style="font-size:13px;margin-top:4px;">${escapeHtml(s.message_to_faculty || "Counseling session scheduled.")}</div>
      </div>
    `;
  }).join("");
}

function renderStudentCounselingMessages() {
  const container = document.getElementById("studentCounselingMessages");
  if (!container) return;

  if (!counselingSessions.length) {
    container.innerHTML = '<div class="text-muted">No counseling sessions scheduled for you yet.</div>';
    return;
  }

  container.innerHTML = counselingSessions.slice(0, 5).map(s => {
    const dt = new Date(s.scheduled_at);
    const whenText = isNaN(dt.getTime()) ? "—" : dt.toLocaleString();
    return `
      <div style="padding:10px 0;border-bottom:1px solid var(--border-color);">
        <div style="font-weight:600;">Session: ${whenText}</div>
        <div class="text-muted" style="font-size:12px;">Status: ${escapeHtml(s.status || "")}</div>
        <div style="font-size:13px;margin-top:4px;">${escapeHtml(s.message_to_student || "Your counselor has scheduled a support session.")}</div>
      </div>
    `;
  }).join("");
}

function renderStudentSupportCards() {
  const counselingEl = document.getElementById("studentSupportCounseling");
  const financialEl = document.getElementById("studentSupportFinancial");
  const academicEl = document.getElementById("studentSupportAcademic");

  if (counselingEl) {
    const latest = counselingSessions
      .slice()
      .sort((a, b) => new Date(b.scheduled_at).getTime() - new Date(a.scheduled_at).getTime())[0];

    if (latest) {
      counselingEl.innerHTML = `${escapeHtml(latest.counselor_name || "Counselor")} · <span class="text-cyan">${escapeHtml(latest.status || "Active")}</span>`;
    } else {
      counselingEl.innerHTML = `No session yet · <span class="text-cyan">Pending</span>`;
    }
  }

  if (financialEl) {
    if (studentFinancialCase) {
      const status = escapeHtml(studentFinancialCase.status || "Under Review");
      const label = escapeHtml(studentFinancialCase.admin_plan_type || "Support Case");
      financialEl.innerHTML = `${label} · <span class="text-cyan">${status}</span>`;
    } else {
      financialEl.innerHTML = `No case yet · <span class="text-cyan">Pending</span>`;
    }
  }

  if (academicEl) {
    const activeCounseling = counselingSessions.some(s => String(s.status || "").toLowerCase() === "active");
    academicEl.innerHTML = activeCounseling
      ? `Follow-up with faculty · <span class="text-cyan">Scheduled</span>`
      : `Learning plan · <span class="text-cyan">In Progress</span>`;
  }
}

function renderStudentActionPlanAndTimeline() {
  const planEl = document.getElementById("studentActionPlanList");
  const timelineEl = document.getElementById("studentSupportTimeline");
  if (!planEl && !timelineEl) return;

  const actions = [];
  const timeline = [];

  const latestActiveCounseling = counselingSessions
    .slice()
    .sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime())
    .find(s => String(s.status || "").toLowerCase() === "active") || null;

  if (latestActiveCounseling) {
    const dt = new Date(latestActiveCounseling.scheduled_at);
    const whenText = isNaN(dt.getTime()) ? "upcoming" : dt.toLocaleString();
    actions.push(`Attend counseling session on ${whenText}.`);
    timeline.push({ title: "Counseling Session", detail: whenText, kind: "Active" });
  }

  if (studentFinancialCase) {
    const status = String(studentFinancialCase.status || "");
    timeline.push({ title: "Financial Support Case", detail: status, kind: "Support" });

    if (status.toLowerCase().includes("awaiting") || status.toLowerCase().includes("input")) {
      actions.push("Submit your fee support details to help admin prepare your support plan.");
    }
    if (studentFinancialCase.admin_plan) {
      actions.push("Review your admin support plan and follow the next payment/scholarship step.");
      timeline.push({ title: "Admin Plan Shared", detail: studentFinancialCase.admin_plan_type || "Support Plan", kind: "Plan" });
    }
  }

  actions.push("Keep attendance consistent this week and complete pending assignments.");

  if (planEl) {
    planEl.innerHTML = `
      <ul style="display:grid;gap:8px;list-style:none;">
        ${actions.slice(0, 5).map(a => `<li style="padding-left:14px;position:relative;"><span style="position:absolute;left:0;top:8px;width:6px;height:6px;border-radius:50%;background:var(--accent-primary);"></span>${escapeHtml(a)}</li>`).join("")}
      </ul>
    `;
  }

  if (timelineEl) {
    if (!timeline.length) {
      timelineEl.innerHTML = '<div class="text-muted">No timeline updates yet.</div>';
    } else {
      timelineEl.innerHTML = timeline.slice(0, 6).map(t => `
        <div style="padding:8px 0;border-bottom:1px solid var(--border-color);">
          <div style="font-weight:600;">${escapeHtml(t.title)}</div>
          <div class="text-muted" style="font-size:12px;">${escapeHtml(t.detail)} · ${escapeHtml(t.kind)}</div>
        </div>
      `).join("");
    }
  }
}

function renderStudentHelpRequests() {
  const container = document.getElementById("studentHelpRequestList");
  if (!container) return;

  const raw = localStorage.getItem("eduguard_student_help_requests");
  const rows = raw ? JSON.parse(raw) : [];

  if (!rows.length) {
    container.innerHTML = '<div class="text-muted">No help requests submitted yet.</div>';
    return;
  }

  container.innerHTML = rows.slice(0, 6).map(r => `
    <div style="padding:8px 0;border-bottom:1px solid var(--border-color);">
      <div style="font-weight:600;">${escapeHtml(r.category)}</div>
      <div class="text-muted" style="font-size:12px;">${escapeHtml(r.time)}</div>
      <div style="font-size:13px;margin-top:4px;">${escapeHtml(r.message)}</div>
    </div>
  `).join("");
}

function submitStudentHelpRequest() {
  const category = document.getElementById("studentHelpCategory")?.value?.trim();
  const message = document.getElementById("studentHelpMessage")?.value?.trim();

  if (!category || !message) {
    alert("Please select category and enter your message.");
    return;
  }

  const raw = localStorage.getItem("eduguard_student_help_requests");
  const rows = raw ? JSON.parse(raw) : [];
  rows.unshift({
    category,
    message,
    time: new Date().toLocaleString(),
  });

  localStorage.setItem("eduguard_student_help_requests", JSON.stringify(rows.slice(0, 20)));

  const categoryEl = document.getElementById("studentHelpCategory");
  const messageEl = document.getElementById("studentHelpMessage");
  if (categoryEl) categoryEl.value = "";
  if (messageEl) messageEl.value = "";

  renderStudentHelpRequests();
  alert("Help request submitted. Your support team will review it.");
}

async function updateStudentTrendCharts() {
  const studentId = studentFinancialCase?.student_id || counselingSessions[0]?.student_id || null;
  if (!studentId) return;

  try {
    const trend = await fetchAPI(`/api/students/${studentId}/risk-trend`);
    const attendancePoints = Array.isArray(trend.attendance_points) ? trend.attendance_points : [];
    const marksPoints = Array.isArray(trend.marks_points) ? trend.marks_points : [];

    const attendanceLabels = attendancePoints.map(p => `Week ${p.week}`);
    const attendanceValues = attendancePoints.map(p => p.value);
    const marksLabels = marksPoints.map(p => `Week ${p.week}`);
    const marksValues = marksPoints.map(p => p.value);

    if (studentAttendanceChart && attendanceLabels.length) {
      studentAttendanceChart.data.labels = attendanceLabels;
      studentAttendanceChart.data.datasets[0].data = attendanceValues;
      studentAttendanceChart.update();
    }

    if (studentMarksChart && marksLabels.length) {
      studentMarksChart.data.labels = marksLabels;
      studentMarksChart.data.datasets[0].data = marksValues;
      studentMarksChart.update();
    }
  } catch (e) {
    // Keep default chart if student trend endpoint is unavailable for this account mapping.
  }
}

async function refreshStudentDashboardEnhancements() {
  renderStudentSupportCards();
  renderStudentActionPlanAndTimeline();
  renderStudentHelpRequests();
  await updateStudentTrendCharts();
}

function getCounselorStudentLastUpdate(studentId) {
  const studentInterventions = interventions
    .filter(iv => iv.studentId === studentId)
    .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

  const latestDate = studentInterventions[0]?.date;
  if (!latestDate) return "No intervention updates";

  const dt = new Date(latestDate);
  return isNaN(dt.getTime()) ? "No intervention updates" : dt.toLocaleDateString();
}

function openInterventionModalWithType(studentId, type) {
  openInterventionModal(studentId);
  const typeSelect = document.getElementById("interventionTypeSelect");
  if (typeSelect) typeSelect.value = type;
}

function populateInterventionStudentSelect() {
  const select = document.getElementById("interventionStudentSelect");
  if (!select) return;

  const options = highRiskStudents.map(s =>
    `<option value="${s.id}">${s.name} — ${s.class}</option>`
  ).join("");

  select.innerHTML = '<option value="">Select student</option>' + options;
}

function openInterventionModal(studentId = null) {
  populateInterventionStudentSelect();

  const select = document.getElementById("interventionStudentSelect");
  if (select) {
    if (studentId) {
      select.value = studentId;
      selectedInterventionStudentId = studentId;
    } else {
      selectedInterventionStudentId = select.value || null;
    }
    select.onchange = () => {
      selectedInterventionStudentId = select.value || null;
    };
  }

  openModal('interventionModal');
}

async function submitIntervention() {
  const studentSelect = document.getElementById("interventionStudentSelect");
  const typeSelect = document.getElementById("interventionTypeSelect");
  const notesEl = document.getElementById("interventionNotes");
  const submitBtn = document.getElementById("assignInterventionBtn");

  const studentId = studentSelect?.value || selectedInterventionStudentId;
  const type = typeSelect?.value;
  const notes = notesEl?.value?.trim() || null;

  if (!studentId) {
    alert("Please select a student.");
    return;
  }

  if (!type) {
    alert("Please select an intervention type.");
    return;
  }

  const originalHtml = submitBtn?.innerHTML;
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Assigning...';
  }

  try {
    const payload = { student_id: studentId, type, notes };
    await fetchAPI('/api/interventions/', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    closeModal('interventionModal');
    if (notesEl) notesEl.value = '';

    const user = getCurrentUser();
    if (user) {
      await fetchDashboardData(user);
      renderAdminTable();
      renderHighRiskTable();
      renderInterventionsTable();
      renderFacultyTable();
      renderCounselorCards();
    }
  } catch (err) {
    alert('Failed to assign intervention: ' + err.message);
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = originalHtml || '<i class="fas fa-check"></i> Assign Intervention';
    }
  }
}

async function openTimelineModal(studentId, studentName) {
  const title = document.getElementById("timelineTitle");
  const body = document.getElementById("timelineBody");

  if (title) title.textContent = `Intervention Timeline — ${studentName}`;
  if (body) {
    body.innerHTML = `
      <div class="timeline-item">
        <div class="timeline-content text-muted">Loading timeline...</div>
      </div>
    `;
  }

  openModal('timelineModal');

  try {
    const events = await fetchAPI(`/api/interventions/${studentId}/timeline`);
    if (!body) return;

    if (!events || !events.length) {
      body.innerHTML = `
        <div class="timeline-item">
          <div class="timeline-content text-muted">No timeline events found.</div>
        </div>
      `;
      return;
    }

    body.innerHTML = events.map(evt => {
      const dt = new Date(evt.recorded_at);
      const dateText = isNaN(dt.getTime()) ? "N/A" : dt.toLocaleDateString();
      return `
        <div class="timeline-item">
          <div class="timeline-date">${dateText}</div>
          <div class="timeline-content"><strong>${evt.event_type}</strong> — ${escapeHtml(evt.description)}</div>
        </div>
      `;
    }).join('');
  } catch (err) {
    if (body) {
      body.innerHTML = `
        <div class="timeline-item">
          <div class="timeline-content text-muted">Failed to load timeline.</div>
        </div>
      `;
    }
  }
}

async function openRiskTrendModal(studentId, studentName) {
  const titleEl = document.getElementById("riskTrendTitle");
  const subtitleEl = document.getElementById("riskTrendSubtitle");
  const attendanceEl = document.getElementById("riskTrendAttendance");
  const marksEl = document.getElementById("riskTrendMarks");
  const feeEl = document.getElementById("riskTrendFee");
  const driversEl = document.getElementById("riskTrendDrivers");
  const rowsEl = document.getElementById("riskTrendRows");

  const normalizeTrend = (raw) => {
    const trend = String(raw || "stable").toLowerCase();
    if (["declining", "decreasing", "down", "worsening"].includes(trend)) return "declining";
    if (["improving", "increasing", "up", "better"].includes(trend)) return "improving";
    return "stable";
  };

  const trendChip = (raw) => {
    const normalized = normalizeTrend(raw);
    const map = {
      declining: { icon: "fa-arrow-trend-down", label: "Declining" },
      improving: { icon: "fa-arrow-trend-up", label: "Improving" },
      stable: { icon: "fa-wave-square", label: "Stable" },
    };
    const meta = map[normalized] || map.stable;
    return `<span class="trend-chip ${normalized}"><i class="fas ${meta.icon}"></i>${meta.label}</span>`;
  };

  if (titleEl) titleEl.textContent = `Risk Trend — ${studentName}`;
  if (subtitleEl) subtitleEl.textContent = "Live trend diagnostics from weekly records";
  if (attendanceEl) attendanceEl.innerHTML = '<span class="trend-chip stable">Loading...</span>';
  if (marksEl) marksEl.innerHTML = '<span class="trend-chip stable">Loading...</span>';
  if (feeEl) feeEl.innerHTML = '<span class="trend-chip stable">Loading...</span>';
  if (driversEl) driversEl.innerHTML = "<li>Loading trend drivers...</li>";
  if (rowsEl) rowsEl.innerHTML = '<tr><td colspan="4" class="text-muted" style="text-align:center;padding:16px;">Loading weekly records...</td></tr>';

  openModal("riskTrendModal");

  try {
    const data = await fetchAPI(`/api/students/${studentId}/risk-trend`);
    if (!data) throw new Error("No data returned");

    if (attendanceEl) attendanceEl.innerHTML = trendChip(data.attendance_trend);
    if (marksEl) marksEl.innerHTML = trendChip(data.marks_trend);
    if (feeEl) feeEl.innerHTML = trendChip(data.fee_trend);

    if (driversEl) {
      const drivers = Array.isArray(data.drivers) ? data.drivers : [];
      driversEl.innerHTML = drivers.map(d => `<li>${escapeHtml(String(d))}</li>`).join("")
        || "<li>No trend drivers detected.</li>";
    }

    if (rowsEl) {
      const attendance = Array.isArray(data.attendance_points) ? data.attendance_points : [];
      const marks = Array.isArray(data.marks_points) ? data.marks_points : [];
      const fee = Array.isArray(data.fee_points) ? data.fee_points : [];
      const weekSet = [...new Set([
        ...attendance.map(p => p.week),
        ...marks.map(p => p.week),
        ...fee.map(p => p.week),
      ])].sort((a, b) => a - b);

      if (!weekSet.length) {
        rowsEl.innerHTML = '<tr><td colspan="4" class="text-muted" style="text-align:center;padding:16px;">No weekly records found.</td></tr>';
      } else {
        rowsEl.innerHTML = weekSet.map(week => {
          const att = attendance.find(p => p.week === week)?.value;
          const mk = marks.find(p => p.week === week)?.value;
          const fs = fee.find(p => p.week === week)?.value;
          const feeStatus = fs === 1 ? '<span class="badge badge-danger">Yes</span>' : fs === 0 ? '<span class="badge badge-cyan">No</span>' : "—";
          return `
            <tr>
              <td>Week ${week}</td>
              <td>${att !== undefined && att !== null ? Number(att).toFixed(1) : "—"}</td>
              <td>${mk !== undefined && mk !== null ? Number(mk).toFixed(1) : "—"}</td>
              <td>${feeStatus}</td>
            </tr>
          `;
        }).join("");

        if (subtitleEl) subtitleEl.textContent = `${weekSet.length} week${weekSet.length === 1 ? "" : "s"} analyzed`;
      }
    }
  } catch (err) {
    if (attendanceEl) attendanceEl.innerHTML = '<span class="trend-chip stable">—</span>';
    if (marksEl) marksEl.innerHTML = '<span class="trend-chip stable">—</span>';
    if (feeEl) feeEl.innerHTML = '<span class="trend-chip stable">—</span>';
    if (driversEl) driversEl.innerHTML = "<li>Failed to load trend details.</li>";
    if (rowsEl) rowsEl.innerHTML = '<tr><td colspan="4" class="text-muted" style="text-align:center;padding:16px;">Failed to load weekly records.</td></tr>';
    if (subtitleEl) subtitleEl.textContent = "Trend diagnostics unavailable";
  }
}

// ===== ROLE-BASED ACCESS CONTROL =====

const roleAccess = {
  admin: ["dashboard", "upload-data", "high-risk", "interventions", "analytics", "agent-copilot", "user-management", "settings"],
  faculty: ["faculty", "upload-data", "high-risk"],
  counselor: ["counselor", "counseling-management", "interventions", "high-risk"],
  student: ["student"]
};

const roleDefaultPage = {
  admin: "dashboard",
  faculty: "faculty",
  counselor: "counselor",
  student: "student"
};

function getCurrentUser() {
  try {
    const stored = localStorage.getItem("eduguard_user");
    if (!stored) return null;
    return JSON.parse(stored);
  } catch (e) {
    return null;
  }
}

function enforceAuth() {
  const user = getCurrentUser();
  if (!user) {
    window.location.href = "login.html";
    return null;
  }
  return user;
}

function canAccessPage(role, page) {
  const pages = roleAccess[role];
  return pages && pages.includes(page);
}

function setupRoleUI(user) {
  if (!user) return;

  const initials = user.name.split(" ").map(w => w[0]).join("").toUpperCase();
  const roleName = user.role.charAt(0).toUpperCase() + user.role.slice(1);

  // Update sidebar user info
  const sidebarAvatar = document.getElementById("sidebarAvatar");
  const sidebarName = document.getElementById("sidebarUserName");
  const sidebarRole = document.getElementById("sidebarUserRole");
  if (sidebarAvatar) sidebarAvatar.textContent = initials;
  if (sidebarName) sidebarName.textContent = user.name;
  if (sidebarRole) sidebarRole.textContent = roleName;

  // Update navbar avatar
  const navAvatar = document.getElementById("navbarAvatar");
  if (navAvatar) navAvatar.textContent = initials;

  // Filter sidebar items based on role
  const allowedPages = roleAccess[user.role] || [];
  document.querySelectorAll(".nav-item[data-page]").forEach(item => {
    const page = item.getAttribute("data-page");
    if (!allowedPages.includes(page)) {
      item.style.display = "none";
    } else {
      item.style.display = "";
    }
  });
}

// ===== PAGE ROUTING =====

function showPage(page) {
  if (page === "reports") page = "analytics";

  const user = getCurrentUser();

  // Role-based protection: redirect to default if unauthorized
  if (user && !canAccessPage(user.role, page)) {
    page = roleDefaultPage[user.role] || "dashboard";
  }

  // Hide all pages
  document.querySelectorAll(".page-section").forEach(el => el.classList.remove("active"));
  // Show target
  const target = document.getElementById("page-" + page);
  if (target) target.classList.add("active");

  // Update nav
  document.querySelectorAll(".nav-item").forEach(el => el.classList.remove("active"));
  document.querySelector(`.nav-item[data-page="${page}"]`)?.classList.add("active");

  // Close sidebar on mobile
  document.getElementById("sidebar").classList.remove("open");

  // Update URL without reload
  const url = new URL(window.location);
  url.searchParams.set("page", page);
  history.replaceState(null, "", url);

  if (user && page === "interventions") {
    (async () => {
      await fetchDashboardData(user);
      renderInterventionsTable();
      renderHighRiskTable();
      renderAdminTable();
    })();
  }

  if (user && (page === "counselor" || page === "counseling-management" || page === "faculty" || page === "student")) {
    (async () => {
      await loadCounselingSessions();
    })();
  }

  if (user && page === "user-management") {
    (async () => {
      await loadUserManagementData();
    })();
  }

  if (user && user.role === 'admin' && page === 'agent-copilot') {
    (async () => {
      await loadCopilotRuns();
    })();
  }

  if (user && user.role === 'admin' && page === 'dashboard') {
    (async () => {
      await loadFinancialCases();
    })();
  }

  if (user && user.role === 'student' && page === 'student') {
    (async () => {
      await loadStudentFinancialSupportCase();
    })();
  }
}

// ===== MODALS =====

function openModal(id) {
  document.getElementById(id).classList.add("active");
}

function closeModal(id) {
  document.getElementById(id).classList.remove("active");
}

// Close modal on overlay click
document.querySelectorAll(".modal-overlay").forEach(overlay => {
  overlay.addEventListener("click", e => {
    if (e.target === overlay) overlay.classList.remove("active");
  });
});

// ===== AI CHAT =====

let aiChatOpen = false;

function toggleAIChat() {
  aiChatOpen = !aiChatOpen;
  document.getElementById("aiChatPanel").classList.toggle("active", aiChatOpen);
}

const aiResponses = [
  "Based on current data, <strong>5 new students</strong> have been flagged as high risk this week. The primary contributing factors are declining attendance and pending tuition fees.",
  "I recommend immediate <strong>counseling intervention</strong> for Rahul Verma (Risk: 92). His attendance has dropped below 50% and he has outstanding financial dues.",
  "The <strong>risk factor analysis</strong> shows that 62% of high-risk students have financial difficulties, followed by 54% with attendance issues. Combining interventions typically improves outcomes by 40%.",
  "Student <strong>Priya Singh</strong> is showing escalating risk trends. Her score rose from 78 to 88 in the last 2 weeks. Family outreach has been suggested as an intervention.",
  "The <strong>intervention success rate</strong> is currently at 67%. Students who receive counseling within 7 days of being flagged show 2.3x better outcomes.",
  "I've analyzed the latest batch of data. <strong>Anita Desai</strong> needs immediate attention — she has 3 concurrent risk factors and no intervention assigned yet.",
];

let aiResponseIndex = 0;

function sendAIMessage() {
  const input = document.getElementById("aiChatInput");
  const msg = input.value.trim();
  if (!msg) return;

  const body = document.getElementById("aiChatBody");

  // User message
  body.innerHTML += `<div class="chat-msg user">${escapeHtml(msg)}</div>`;
  input.value = "";

  // Typing indicator
  body.innerHTML += `<div class="chat-msg ai" id="typing" style="opacity:0.6;">
    <i class="fas fa-circle-notch fa-spin"></i> Analyzing...
  </div>`;
  body.scrollTop = body.scrollHeight;

  // AI response after delay
  setTimeout(() => {
    const typing = document.getElementById("typing");
    if (typing) typing.remove();

    const response = aiResponses[aiResponseIndex % aiResponses.length];
    aiResponseIndex++;

    body.innerHTML += `<div class="chat-msg ai">${response}</div>`;
    body.scrollTop = body.scrollHeight;
  }, 1200);
}

function escapeHtml(text) {
  const d = document.createElement("div");
  d.textContent = text;
  return d.innerHTML;
}

// ===== MOBILE SIDEBAR =====

document.getElementById("mobileToggle")?.addEventListener("click", () => {
  document.getElementById("sidebar").classList.toggle("open");
});

document.getElementById("sidebarClose")?.addEventListener("click", () => {
  document.getElementById("sidebar").classList.remove("open");
});

// ===== CHARTS =====

function initCharts() {
  const compactYAxis = {
    ticks: {
      color: "#6B7280",
      font: { family: "Inter", size: 9 },
      padding: 1,
      maxTicksLimit: 10,
      autoSkip: false,
    },
    grid: { color: "rgba(255,255,255,0.04)" },
  };

  const chartDefaults = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        labels: {
          color: "#9CA3AF",
          font: { family: "Inter", size: 12 },
          padding: 16,
        },
      },
      tooltip: {
        backgroundColor: "#1F2937",
        titleColor: "#E5E7EB",
        bodyColor: "#9CA3AF",
        borderColor: "rgba(255,255,255,0.06)",
        borderWidth: 1,
        cornerRadius: 8,
        padding: 12,
        titleFont: { family: "Inter", weight: 600 },
        bodyFont: { family: "Inter" },
      },
    },
    scales: {
      x: {
        ticks: { color: "#6B7280", font: { family: "Inter", size: 11 } },
        grid: { color: "rgba(255,255,255,0.04)" },
      },
      y: compactYAxis,
    },
  };

  // Student Attendance Chart
  const attCtx = document.getElementById("attendanceChart");
  if (attCtx) {
    studentAttendanceChart = new Chart(attCtx.getContext("2d"), {
      type: "line",
      data: {
        labels: ["Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb"],
        datasets: [{
          label: "Attendance %",
          data: [82, 75, 68, 60, 55, 50, 48],
          borderColor: "#EF4444",
          backgroundColor: "rgba(239,68,68,0.08)",
          fill: true,
          tension: 0.4,
          pointBackgroundColor: "#EF4444",
          pointRadius: 4,
          pointHoverRadius: 6,
          borderWidth: 2,
        }]
      },
      options: {
        ...chartDefaults,
        maintainAspectRatio: true,
        aspectRatio: 2.6,
      },
    });
  }

  // Student Marks Chart
  const mkCtx = document.getElementById("marksChart");
  if (mkCtx) {
    studentMarksChart = new Chart(mkCtx.getContext("2d"), {
      type: "line",
      data: {
        labels: ["IA-1", "IA-2", "IA-3", "Midterm", "IA-4", "IA-5"],
        datasets: [{
          label: "Marks",
          data: [65, 58, 48, 42, 38, 32],
          borderColor: "#EF4444",
          backgroundColor: "rgba(239,68,68,0.08)",
          fill: true,
          tension: 0.4,
          pointBackgroundColor: "#EF4444",
          pointRadius: 4,
          pointHoverRadius: 6,
          borderWidth: 2,
        }]
      },
      options: { ...chartDefaults },
    });
  }

  // Analytics: Risk Trend Over Time
  const rtCtx = document.getElementById("riskTrendChart");
  if (rtCtx) {
    rtCtx.style.height = "76px";
    rtCtx.style.maxHeight = "76px";
    const trendLabels = analyticsData?.risk_trend?.map(p => p.month) || [];
    const trendCounts = analyticsData?.risk_trend?.map(p => p.count) || [];
    new Chart(rtCtx.getContext("2d"), {
      type: "line",
      data: {
        labels: trendLabels,
        datasets: [{
          label: "High Risk Students",
          data: trendCounts,
          borderColor: "#EF4444",
          backgroundColor: "rgba(239,68,68,0.08)",
          fill: true,
          tension: 0.4,
          pointBackgroundColor: "#EF4444",
          pointRadius: 5,
          pointHoverRadius: 7,
          borderWidth: 2.5,
        }]
      },
      options: {
        ...chartDefaults,
        plugins: {
          ...chartDefaults.plugins,
          legend: { display: false },
        },
        layout: {
          padding: {
            left: 0,
            right: 4,
            top: 0,
            bottom: 0,
          },
        },
        scales: {
          ...chartDefaults.scales,
          x: {
            ...chartDefaults.scales.x,
            offset: false,
          },
          y: {
            ...chartDefaults.scales.y,
            ticks: {
              ...chartDefaults.scales.y.ticks,
              padding: 1,
              maxTicksLimit: 10,
              autoSkip: false,
            },
          },
        },
      },
    });
  }

  // Analytics: Intervention Success
  const isCtx = document.getElementById("interventionChart");
  if (isCtx) {
    isCtx.style.height = "76px";
    isCtx.style.maxHeight = "76px";
    const interventionSuccess = analyticsData?.intervention_success || {
      improved: 0,
      stable: 0,
      no_change: 0,
      declined: 0,
    };
    new Chart(isCtx.getContext("2d"), {
      type: "doughnut",
      data: {
        labels: ["Improved", "Stable", "No Change", "Declined"],
        datasets: [{
          data: [
            interventionSuccess.improved,
            interventionSuccess.stable,
            interventionSuccess.no_change,
            interventionSuccess.declined,
          ],
          backgroundColor: [
            "#38BDF8",
            "#2563EB",
            "#6B7280",
            "#EF4444",
          ],
          borderColor: "#1F2937",
          borderWidth: 3,
          hoverOffset: 8,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "right",
            labels: {
              color: "#9CA3AF",
              font: { family: "Inter", size: 12 },
              padding: 16,
              usePointStyle: true,
              pointStyleWidth: 10,
            },
          },
          tooltip: chartDefaults.plugins.tooltip,
        },
      },
    });
  }

  // Analytics: Risk Factor Distribution
  const rfCtx = document.getElementById("factorChart");
  if (rfCtx) {
    rfCtx.style.height = "84px";
    rfCtx.style.maxHeight = "84px";
    const factorDistribution = analyticsData?.factor_distribution || {
      financial: 0,
      attendance: 0,
      academic: 0,
      family: 0,
    };
    new Chart(rfCtx.getContext("2d"), {
      type: "bar",
      data: {
        labels: ["Financial", "Attendance", "Academic", "Family"],
        datasets: [{
          label: "Number of High Risk Students",
          data: [
            factorDistribution.financial,
            factorDistribution.attendance,
            factorDistribution.academic,
            factorDistribution.family,
          ],
          backgroundColor: [
            "rgba(239,68,68,0.7)",
            "rgba(245,158,11,0.7)",
            "rgba(139,92,246,0.7)",
            "rgba(236,72,153,0.7)",
          ],
          borderColor: [
            "#EF4444",
            "#F59E0B",
            "#8B5CF6",
            "#EC4899",
          ],
          borderWidth: 1,
          borderRadius: 8,
          barThickness: 28,
        }]
      },
      options: {
        ...chartDefaults,
        layout: {
          padding: {
            left: 0,
            right: 4,
            top: 0,
            bottom: 0,
          },
        },
        plugins: {
          ...chartDefaults.plugins,
          legend: { display: false },
        },
        scales: {
          ...chartDefaults.scales,
          x: {
            ...chartDefaults.scales.x,
            offset: false,
            ticks: {
              ...chartDefaults.scales.x.ticks,
              padding: 2,
            },
          },
          y: {
            ...chartDefaults.scales.y,
            beginAtZero: true,
            ticks: {
              ...chartDefaults.scales.y.ticks,
              padding: 1,
              maxTicksLimit: 10,
              autoSkip: false,
            },
          },
        },
      },
    });
  }
}

// ===== RISK CIRCLE ANIMATION =====

function animateRiskCircle() {
  const fill = document.getElementById("riskCircleFill");
  if (!fill) return;
  const score = 78;
  const circumference = 2 * Math.PI * 90; // r=90
  const offset = circumference - (score / 100) * circumference;
  setTimeout(() => {
    fill.style.strokeDashoffset = offset;
  }, 300);
}

// ===== UPLOAD DATA (Dual-Tab: Admission + Weekly) =====

let uploadCurrentFile = null;
let uploadCurrentType = "admission"; // "admission" or "weekly"
let facultyWeeklyUploadFile = null;

const ADMISSION_COLS = ["id", "name", "class_name", "semester", "Family_Income", "Scholarship", "Education_Loan", "Father_Occupation", "Mother_Occupation", "Parent_Education", "Home_Location", "HighSchool_Grade", "Admission_Quota"];
const WEEKLY_COLS = ["Student_ID", "Week_Number", "Attendance_Percentage", "IA_Marks", "Semester_Marks", "Backlog_Count", "Fee_Outstanding"];

function initializeFacultyWeekDropdown() {
  const select = document.getElementById("facultyWeekSelect");
  if (!select) return;
  if (select.options.length > 1) return;

  for (let week = 1; week <= 16; week++) {
    const option = document.createElement("option");
    option.value = String(week);
    option.textContent = `Week ${week}`;
    select.appendChild(option);
  }
}

function initializeWeeklyUploadWeekDropdown() {
  const select = document.getElementById("weeklyUploadWeekSelect");
  if (!select) return;
  if (select.options.length > 1) return;

  for (let week = 1; week <= 16; week++) {
    const option = document.createElement("option");
    option.value = String(week);
    option.textContent = `Week ${week}`;
    select.appendChild(option);
  }
}

function refreshWeeklyPreviewWithWeek() {
  if (uploadCurrentType !== "weekly" || !uploadCurrentFile) return;

  const reader = new FileReader();
  reader.onload = function (e) {
    try {
      const content = e.target.result;
      const rows = uploadCurrentFile.name.toLowerCase().endsWith(".json")
        ? parseJSONUpload(content)
        : parseCSVUpload(content);
      renderUploadPreview(rows);
    } catch (_) {
      // no-op
    }
  };
  reader.readAsText(uploadCurrentFile);
}

function handleFacultyWeeklyFile(event) {
  const file = event.target.files?.[0];
  facultyWeeklyUploadFile = file || null;
  const label = document.getElementById("facultyWeeklyFileName");
  if (label) {
    label.textContent = file
      ? `${file.name} (${(file.size / 1024).toFixed(1)} KB)`
      : "No file selected";
  }
}

function buildWeeklyCsvForWeek(rows, selectedWeek) {
  const normalizedRows = rows.map(row => {
    const normalized = { ...row };
    if (!normalized.Student_ID && normalized.id) normalized.Student_ID = normalized.id;
    normalized.Week_Number = String(selectedWeek);
    if (normalized.Fee_Outstanding === undefined || normalized.Fee_Outstanding === null || normalized.Fee_Outstanding === "") {
      normalized.Fee_Outstanding = "No";
    }
    return normalized;
  });

  const missingStudent = normalizedRows.findIndex(r => !r.Student_ID);
  const missingAttendance = normalizedRows.findIndex(r => r.Attendance_Percentage === undefined || r.Attendance_Percentage === "");
  if (missingStudent !== -1) {
    throw new Error(`Row ${missingStudent + 1} missing Student_ID (or id).`);
  }
  if (missingAttendance !== -1) {
    throw new Error(`Row ${missingAttendance + 1} missing Attendance_Percentage.`);
  }

  const header = WEEKLY_COLS.join(",");
  const lines = normalizedRows.map(r =>
    WEEKLY_COLS.map(col => String(r[col] ?? "").replaceAll(",", " ")).join(",")
  );
  return [header, ...lines].join("\n");
}

async function submitFacultyWeeklyUpload() {
  const weekSelect = document.getElementById("facultyWeekSelect");
  const submitBtn = document.getElementById("facultyWeeklySubmitBtn");
  const selectedWeek = Number(weekSelect?.value || 0);

  if (!selectedWeek) {
    alert("Please select a week number.");
    return;
  }
  if (!facultyWeeklyUploadFile) {
    alert("Please select a weekly file first.");
    return;
  }

  const originalHtml = submitBtn?.innerHTML;
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Uploading...';
  }

  try {
    const text = await facultyWeeklyUploadFile.text();
    const rows = facultyWeeklyUploadFile.name.toLowerCase().endsWith(".json")
      ? parseJSONUpload(text)
      : parseCSVUpload(text);

    const weeklyCsv = buildWeeklyCsvForWeek(rows, selectedWeek);
    const blob = new Blob([weeklyCsv], { type: "text/csv" });
    const file = new File([blob], `weekly_week_${selectedWeek}.csv`, { type: "text/csv" });

    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch("http://127.0.0.1:8000/api/upload/weekly", {
      method: "POST",
      headers: getAuthHeaders(),
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Server error ${res.status}`);
    }

    const result = await res.json();
    alert(`Weekly upload complete: Created ${result.created}, Updated/Skipped ${result.skipped}, Errors ${result.errors?.length || 0}`);
    closeModal("uploadModal");

    const user = getCurrentUser();
    if (user) {
      await fetchDashboardData(user);
      renderAdminTable();
      renderHighRiskTable();
      renderInterventionsTable();
      renderFacultyTable();
      renderCounselorCards();
    }
  } catch (err) {
    alert("Weekly upload failed: " + err.message);
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = originalHtml || '<i class="fas fa-upload"></i> Submit Weekly Data';
    }
  }
}

function switchUploadType(type) {
  uploadCurrentType = type;
  clearUploadFile();
  document.getElementById("tabAdmission").classList.toggle("active", type === "admission");
  document.getElementById("tabWeekly").classList.toggle("active", type === "weekly");
  document.getElementById("uploadAdmissionSection").style.display = type === "admission" ? "" : "none";
  document.getElementById("uploadWeeklySection").style.display = type === "weekly" ? "" : "none";
}

function _getUploadElements() {
  if (uploadCurrentType === "weekly") {
    return {
      dropZone: document.getElementById("uploadDropZoneWeekly"),
      fileInfo: document.getElementById("uploadFileInfoWeekly"),
      fileName: document.getElementById("uploadFileNameWeekly"),
      fileSize: document.getElementById("uploadFileSizeWeekly"),
      fileInput: document.getElementById("uploadFileInputWeekly"),
    };
  }
  return {
    dropZone: document.getElementById("uploadDropZone"),
    fileInfo: document.getElementById("uploadFileInfo"),
    fileName: document.getElementById("uploadFileName"),
    fileSize: document.getElementById("uploadFileSize"),
    fileInput: document.getElementById("uploadFileInput"),
  };
}

function handleUploadFile(event) {
  const file = event.target.files[0];
  if (!file) return;
  uploadCurrentFile = file;

  // Auto-detect type from input id
  if (event.target.id === "uploadFileInputWeekly") uploadCurrentType = "weekly";
  else if (event.target.id === "uploadFileInput") uploadCurrentType = "admission";

  const els = _getUploadElements();
  if (els.dropZone) els.dropZone.style.display = "none";
  if (els.fileInfo) els.fileInfo.style.display = "flex";
  if (els.fileName) els.fileName.textContent = file.name;
  if (els.fileSize) els.fileSize.textContent = (file.size / 1024).toFixed(1) + " KB";

  document.getElementById("uploadResultsCard").style.display = "none";

  const reader = new FileReader();
  reader.onload = function (e) {
    try {
      const content = e.target.result;
      let rows;
      if (file.name.toLowerCase().endsWith(".json")) {
        rows = parseJSONUpload(content);
      } else {
        rows = parseCSVUpload(content);
      }
      renderUploadPreview(rows);
    } catch (err) {
      alert("Failed to parse file: " + err.message);
    }
  };
  reader.readAsText(file);
}

function clearUploadFile() {
  uploadCurrentFile = null;
  // Reset admission elements
  const dz = document.getElementById("uploadDropZone");
  if (dz) dz.style.display = "";
  const fi = document.getElementById("uploadFileInfo");
  if (fi) fi.style.display = "none";
  const inp = document.getElementById("uploadFileInput");
  if (inp) inp.value = "";
  // Reset weekly elements
  const dz2 = document.getElementById("uploadDropZoneWeekly");
  if (dz2) dz2.style.display = "";
  const fi2 = document.getElementById("uploadFileInfoWeekly");
  if (fi2) fi2.style.display = "none";
  const inp2 = document.getElementById("uploadFileInputWeekly");
  if (inp2) inp2.value = "";
  // Hide shared panels
  const pc = document.getElementById("uploadPreviewCard");
  if (pc) pc.style.display = "none";
  const rc = document.getElementById("uploadResultsCard");
  if (rc) rc.style.display = "none";
}

function parseCSVUpload(content) {
  const lines = content.split(/\r?\n/).filter(l => l.trim());
  if (lines.length < 2) throw new Error("CSV must have a header row and at least one data row.");
  const headers = lines[0].split(",").map(h => h.trim());
  const rows = [];
  for (let i = 1; i < lines.length; i++) {
    const values = lines[i].split(",").map(v => v.trim());
    const row = {};
    headers.forEach((h, idx) => row[h] = values[idx] || "");
    rows.push(row);
  }
  return rows;
}

function parseJSONUpload(content) {
  const data = JSON.parse(content);
  if (Array.isArray(data)) return data;
  for (const key of ["students", "data", "records"]) {
    if (data[key] && Array.isArray(data[key])) return data[key];
  }
  throw new Error("JSON must be an array or contain a 'students'/'data'/'records' key.");
}

function renderUploadPreview(rows) {
  const card = document.getElementById("uploadPreviewCard");
  const head = document.getElementById("uploadPreviewHead");
  const body = document.getElementById("uploadPreviewBody");
  const count = document.getElementById("uploadRowCount");

  if (!rows.length) { card.style.display = "none"; return; }
  card.style.display = "";
  count.textContent = rows.length + " row" + (rows.length === 1 ? "" : "s");

  // Use appropriate columns based on upload type
  const cols = uploadCurrentType === "weekly" ? WEEKLY_COLS : ADMISSION_COLS;
  const selectedWeek = uploadCurrentType === "weekly"
    ? Number(document.getElementById("weeklyUploadWeekSelect")?.value || 0)
    : 0;

  let previewRows = rows;
  if (uploadCurrentType === "weekly" && selectedWeek) {
    previewRows = rows.map(r => ({ ...r, Week_Number: String(selectedWeek) }));
  }

  head.innerHTML = cols.map(c => `<th>${c}</th>`).join("");
  body.innerHTML = previewRows.slice(0, 50).map(r => {
    return "<tr>" + cols.map(c => {
      let val = r[c] !== undefined && r[c] !== "" ? r[c] : "—";
      return `<td>${escapeHtml(String(val))}</td>`;
    }).join("") + "</tr>";
  }).join("");

  if (previewRows.length > 50) {
    body.innerHTML += `<tr><td colspan="${cols.length}" style="text-align:center;color:var(--text-secondary);font-style:italic;">...and ${previewRows.length - 50} more rows</td></tr>`;
  }
}

async function submitUploadData() {
  if (!uploadCurrentFile) { alert("Please select a file first."); return; }

  const btn = document.getElementById("submitUploadBtn");
  btn.disabled = true;
  const label = uploadCurrentType === "weekly" ? "Weekly" : "Admission";
  btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Uploading ${label} Data...`;

  // Pick endpoint based on current tab
  const endpoint = uploadCurrentType === "weekly"
    ? "http://127.0.0.1:8000/api/upload/weekly"
    : "http://127.0.0.1:8000/api/upload/admission";

  try {
    const token = localStorage.getItem("eduguard_token");
    const formData = new FormData();

    if (uploadCurrentType === "weekly") {
      const selectedWeek = Number(document.getElementById("weeklyUploadWeekSelect")?.value || 0);
      if (!selectedWeek) {
        throw new Error("Please select a week number.");
      }

      const content = await uploadCurrentFile.text();
      const rows = uploadCurrentFile.name.toLowerCase().endsWith(".json")
        ? parseJSONUpload(content)
        : parseCSVUpload(content);

      const weeklyCsv = buildWeeklyCsvForWeek(rows, selectedWeek);
      const weeklyBlob = new Blob([weeklyCsv], { type: "text/csv" });
      const weeklyFile = new File([weeklyBlob], `weekly_week_${selectedWeek}.csv`, { type: "text/csv" });
      formData.append("file", weeklyFile);
    } else {
      formData.append("file", uploadCurrentFile);
    }

    const res = await fetch(endpoint, {
      method: "POST",
      headers: token ? { "Authorization": `Bearer ${token}` } : {},
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Server error ${res.status}`);
    }

    const result = await res.json();
    showUploadResults(result);
  } catch (err) {
    alert("Upload failed: " + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="fas fa-upload"></i> Submit & Run Risk Prediction';
  }
}

function showUploadResults(result) {
  const card = document.getElementById("uploadResultsCard");
  card.style.display = "";
  document.getElementById("resultCreated").textContent = result.created;
  document.getElementById("resultSkipped").textContent = result.skipped;
  document.getElementById("resultErrors").textContent = result.errors ? result.errors.length : 0;

  const errorsList = document.getElementById("uploadErrorsList");
  const errorsContent = document.getElementById("uploadErrorsContent");
  if (result.errors && result.errors.length) {
    errorsList.style.display = "";
    errorsContent.innerHTML = result.errors.map(e => `<div style="margin-bottom:4px;">⚠ ${escapeHtml(e)}</div>`).join("");
  } else {
    errorsList.style.display = "none";
  }
  card.scrollIntoView({ behavior: "smooth", block: "start" });
}

// Drag and drop — both zones
document.addEventListener("DOMContentLoaded", () => {
  function setupDragDrop(zoneId, inputId) {
    const zone = document.getElementById(zoneId);
    if (!zone) return;
    ["dragenter", "dragover"].forEach(evt => zone.addEventListener(evt, e => {
      e.preventDefault(); zone.classList.add("drag-over");
    }));
    ["dragleave", "drop"].forEach(evt => zone.addEventListener(evt, e => {
      e.preventDefault(); zone.classList.remove("drag-over");
    }));
    zone.addEventListener("drop", e => {
      const file = e.dataTransfer.files[0];
      if (file) {
        const input = document.getElementById(inputId);
        const dt = new DataTransfer();
        dt.items.add(file);
        input.files = dt.files;
        handleUploadFile({ target: input });
      }
    });
  }
  setupDragDrop("uploadDropZone", "uploadFileInput");
  setupDragDrop("uploadDropZoneWeekly", "uploadFileInputWeekly");
});

// ===== INIT =====

document.addEventListener("DOMContentLoaded", async () => {
  // --- Authentication Gate ---
  const user = enforceAuth();
  if (!user) return; // redirecting to login.html

  // --- Setup role-based UI ---
  setupRoleUI(user);

  // --- Fetch Data ---
  await fetchDashboardData(user);
  await loadCounselingSessions();
  await loadSettings();
  initializeFacultyWeekDropdown();
  initializeWeeklyUploadWeekDropdown();

  // --- Render tables & charts ---
  renderAdminTable();
  renderHighRiskTable();
  renderInterventionsTable();
  renderFacultyTable();
  renderCounselorCards();
  await loadStudentFinancialSupportCase();
  initCharts();
  await refreshStudentDashboardEnhancements();
  animateRiskCircle();

  // --- Route to correct page from URL or default ---
  const params = new URLSearchParams(window.location.search);
  let targetPage = params.get("page") || roleDefaultPage[user.role] || "dashboard";

  // Enforce role access
  if (!canAccessPage(user.role, targetPage)) {
    targetPage = roleDefaultPage[user.role] || "dashboard";
  }

  showPage(targetPage);
});
