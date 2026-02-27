/* ==========================================
   EduGuard AI - Authentication Logic
   Connects to FastAPI backend at /api/auth/login
   Falls back to mock data if backend unavailable
   ========================================== */

const API_BASE = "http://127.0.0.1:8000/api";

// ===== FALLBACK MOCK USERS (if backend is offline) =====

const mockUsers = [
    { id: "admin1", email: "admin@eduguard.com", password: "admin123", role: "admin", name: "Dr. Arun Kumar" },
    { id: "faculty1", email: "faculty@eduguard.com", password: "faculty123", role: "faculty", name: "Prof. Meena" },
    { id: "counselor1", email: "counselor@eduguard.com", password: "counselor123", role: "counselor", name: "Dr. Ravi" },
    { id: "student1", email: "student@eduguard.com", password: "student123", role: "student", name: "Arjun" },
];

// ===== ROLE → PAGE MAPPING =====

const rolePageMap = {
    admin: "dashboard",
    faculty: "faculty",
    counselor: "counselor",
    student: "student"
};

// ===== STATE =====

let selectedRole = null;

// ===== AUTO-REDIRECT IF ALREADY LOGGED IN =====

(function checkExistingSession() {
    if (!document.querySelector(".login-page")) return;
    const stored = localStorage.getItem("eduguard_user");
    if (stored) {
        try {
            const user = JSON.parse(stored);
            if (user && user.role && rolePageMap[user.role]) {
                window.location.href = "index.html?page=" + rolePageMap[user.role];
            }
        } catch (e) {
            localStorage.removeItem("eduguard_user");
        }
    }
})();

// ===== ROLE SELECTION =====

function selectRole(role, el) {
    selectedRole = role;
    document.querySelectorAll(".role-card").forEach(c => c.classList.remove("selected"));
    el.classList.add("selected");
    hideError();
    validateForm();
}

// ===== FORM VALIDATION =====

function validateForm() {
    const email = document.getElementById("loginEmail").value.trim();
    const password = document.getElementById("loginPassword").value.trim();
    const btn = document.getElementById("loginBtn");
    btn.disabled = !(email && password && selectedRole);
}

document.getElementById("loginEmail")?.addEventListener("input", validateForm);
document.getElementById("loginPassword")?.addEventListener("input", validateForm);

// ===== PASSWORD TOGGLE =====

function togglePassword() {
    const input = document.getElementById("loginPassword");
    const icon = document.getElementById("passwordToggleIcon");
    if (input.type === "password") {
        input.type = "text";
        icon.classList.replace("fa-eye", "fa-eye-slash");
    } else {
        input.type = "password";
        icon.classList.replace("fa-eye-slash", "fa-eye");
    }
}

// ===== LOGIN — tries real backend, falls back to mock =====

async function tryBackendLogin(email, password, role) {
    try {
        const res = await fetch(`${API_BASE}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password, role }),
        });

        if (!res.ok) return null;

        const data = await res.json();
        if (!data.access_token || !data.user) return null;

        // Check role matches
        if (data.user.role !== role) return null;

        return {
            id: data.user.id || email,
            email: data.user.email || email,
            role: data.user.role,
            name: data.user.name || email,
            token: data.access_token,
            loginTime: new Date().toISOString(),
            source: "backend",
        };
    } catch (err) {
        // Backend unavailable — will fall through to mock
        return null;
    }
}

function tryMockLogin(email, password, role) {
    const user = mockUsers.find(u =>
        (u.email === email || u.id === email) &&
        u.password === password &&
        u.role === role
    );
    if (!user) return null;
    return {
        id: user.id,
        email: user.email,
        role: user.role,
        name: user.name,
        token: null,
        loginTime: new Date().toISOString(),
        source: "mock",
    };
}

async function handleLogin(e) {
    e.preventDefault();

    const email = document.getElementById("loginEmail").value.trim();
    const password = document.getElementById("loginPassword").value.trim();
    const btn = document.getElementById("loginBtn");

    if (!selectedRole) { showError("Please select a role to continue."); return; }
    if (!email || !password) { showError("Please enter your email and password."); return; }

    btn.classList.add("loading");
    btn.disabled = true;
    hideError();

    // Try real backend first, then mock
    let session = await tryBackendLogin(email, password, selectedRole);
    if (!session) {
        session = tryMockLogin(email, password, selectedRole);
    }

    if (session) {
        if (session.token) {
            localStorage.setItem("eduguard_token", session.token);
        } else {
            localStorage.removeItem("eduguard_token");
        }
        localStorage.setItem("eduguard_user", JSON.stringify(session));
        window.location.href = "index.html?page=" + rolePageMap[session.role];
    } else {
        showError("Invalid credentials. Please check your email, password, and selected role.");
        btn.classList.remove("loading");
        btn.disabled = false;
    }
}

// ===== ERROR DISPLAY =====

function showError(msg) {
    const errorEl = document.getElementById("loginError");
    const textEl = document.getElementById("loginErrorText");
    textEl.textContent = msg;
    errorEl.classList.remove("visible");
    void errorEl.offsetWidth;
    errorEl.classList.add("visible");
}

function hideError() {
    document.getElementById("loginError")?.classList.remove("visible");
}

// ===== QUICK DEMO LOGIN =====

function fillDemo(role) {
    const user = mockUsers.find(u => u.role === role);
    if (!user) return;
    const roleCard = document.querySelector(`.role-card[data-role="${role}"]`);
    if (roleCard) selectRole(role, roleCard);
    document.getElementById("loginEmail").value = user.email;
    document.getElementById("loginPassword").value = user.password;
    validateForm();
}

// ===== GLOBAL AUTH UTILITIES =====

function getCurrentUser() {
    try {
        const stored = localStorage.getItem("eduguard_user");
        if (!stored) return null;
        return JSON.parse(stored);
    } catch (e) {
        return null;
    }
}

function getLoggedInUser() {
    return getCurrentUser();
}

function enforceAuth() {
    const user = getCurrentUser();
    if (!user) {
        window.location.href = "login.html";
        return null;
    }
    return user;
}

function logout() {
    localStorage.removeItem("eduguard_user");
    localStorage.removeItem("eduguard_token");
    window.location.href = "login.html";
}

// ===== API HELPER (for app.js to use) =====

async function apiFetch(path, options = {}) {
    const user = getCurrentUser();
    const headers = { "Content-Type": "application/json", ...options.headers };
    if (user && user.token) {
        headers["Authorization"] = `Bearer ${user.token}`;
    }
    try {
        const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
        if (res.status === 401) { logout(); return null; }
        if (!res.ok) return null;
        return await res.json();
    } catch (err) {
        return null;  // backend offline — caller uses mock data
    }
}

window.apiFetch = apiFetch;
window.getCurrentUser = getCurrentUser;
window.enforceAuth = enforceAuth;
window.logout = logout;
