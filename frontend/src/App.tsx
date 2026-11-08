import React, { useEffect, useState } from "react";
import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid";
import timeGridPlugin from "@fullcalendar/timegrid";
import interactionPlugin from "@fullcalendar/interaction";
import type {
  ScheduleItem,
  ConflictAlert,
  NLPParsedOutput,
  TaskItem,
  StudyPlanItem,
  DailyLoadItem,
  SemesterPlanItem,
} from "./api";

const API_BASE = "http://localhost:8000/api";

const TYPE_COLORS: Record<string, string> = {
  class: "#2563eb",
  exam: "#dc2626",
  study: "#16a34a",
  event: "#7c3aed",
};

const pad = (n: number) => String(n).padStart(2, "0");
const toLocal = (d: Date) =>
  `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:00`;

// Optimized input sizes (not too big, not too small)
const inputStyle = {
  padding: "10px 14px",
  borderRadius: "6px",
  border: "1px solid #cbd5e1",
  color: "#0f172a",
  backgroundColor: "#ffffff",
  width: "100%",
  boxSizing: "border-box" as const,
  fontSize: "14px",
};

export default function App() {
  const [activeTab, setActiveTab] = useState<"calendar" | "study" | "workload" | "semester">("calendar");

  // JWT Auth State
  const [token, setToken] = useState<string | null>(localStorage.getItem("jwt_token"));
  const [userName, setUserName] = useState<string>(localStorage.getItem("user_name") || "Demo Student");
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [isRegister, setIsRegister] = useState(false);
  const [authName, setAuthName] = useState("");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");

  // AI Settings State
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [apiBaseUrl, setApiBaseUrl] = useState(localStorage.getItem("llm_base_url") || "");
  const [apiKey, setApiKey] = useState(localStorage.getItem("llm_api_key") || "");
  const [apiModel, setApiModel] = useState(localStorage.getItem("llm_model") || "");
  const [testStatus, setTestStatus] = useState<{ type: "success" | "error" | "loading"; msg: string } | null>(null);

  // Core Data State
  const [schedules, setSchedules] = useState<ScheduleItem[]>([]);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [studyPlans, setStudyPlans] = useState<StudyPlanItem[]>([]);
  const [dailyLoad, setDailyLoad] = useState<DailyLoadItem[]>([]);
  const [balanceLogs, setBalanceLogs] = useState<string[]>([]);
  const [semesterPlans, setSemesterPlans] = useState<SemesterPlanItem[]>([]);

  // NLP & Conflict State
  const [nlpInput, setNlpInput] = useState("");
  const [nlpLoading, setNlpLoading] = useState(false);
  const [parsedPreview, setParsedPreview] = useState<NLPParsedOutput | null>(null);
  const [conflict, setConflict] = useState<ConflictAlert | null>(null);
  const [pendingEvent, setPendingEvent] = useState<{
    title: string;
    type: string;
    start_time: string;
    end_time: string;
  } | null>(null);

  // Manual Schedule Form
  const [title, setTitle] = useState("");
  const [type, setType] = useState<"class" | "exam" | "event" | "study">("study");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");

  // Task Form
  const [taskTitle, setTaskTitle] = useState("");
  const [taskDesc, setTaskDesc] = useState("");
  const [taskPriority, setTaskPriority] = useState<"low" | "medium" | "high">("high");
  const [taskHours, setTaskHours] = useState(4);
  const [taskDeadline, setTaskDeadline] = useState("");
  const [generatingTaskId, setGeneratingTaskId] = useState<string | null>(null);

  // Semester Form
  const [semStart, setSemStart] = useState("2026-09-01T08:00");
  const [semEnd, setSemEnd] = useState("2026-12-20T18:00");
  const [semEventTitle, setSemEventTitle] = useState("");
  const [semEventType, setSemEventType] = useState("exam");
  const [semEventDate, setSemEventDate] = useState("");
  const [semStatusMsg, setSemStatusMsg] = useState("");

  const authHeaders = () => {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    if (apiKey.trim()) {
      headers["X-LLM-Api-Key"] = apiKey.trim();
      headers["X-LLM-Base-Url"] = apiBaseUrl.trim();
      headers["X-LLM-Model"] = apiModel.trim();
    }
    return headers;
  };

  const refreshAll = async () => {
    const [sRes, tRes, spRes, wRes, semRes] = await Promise.all([
      fetch(`${API_BASE}/schedules`, { headers: authHeaders() }),
      fetch(`${API_BASE}/tasks`, { headers: authHeaders() }),
      fetch(`${API_BASE}/study-plans`, { headers: authHeaders() }),
      fetch(`${API_BASE}/workload/summary`, { headers: authHeaders() }),
      fetch(`${API_BASE}/semester-plans`, { headers: authHeaders() }),
    ]);
    if (sRes.ok) setSchedules(await sRes.json());
    if (tRes.ok) setTasks(await tRes.json());
    if (spRes.ok) setStudyPlans(await spRes.json());
    if (wRes.ok) setDailyLoad(await wRes.json());
    if (semRes.ok) setSemesterPlans(await semRes.json());
  };

  useEffect(() => {
    refreshAll();
  }, [token]);

  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const endpoint = isRegister ? "/auth/register" : "/auth/login";
    const body = isRegister
      ? { name: authName, email: authEmail, password: authPassword }
      : { email: authEmail, password: authPassword };

    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (res.ok) {
      const data = await res.json();
      localStorage.setItem("jwt_token", data.access_token);
      localStorage.setItem("user_name", data.user.name);
      setToken(data.access_token);
      setUserName(data.user.name);
      setShowAuthModal(false);
    } else {
      alert("Authentication failed. Check credentials.");
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("jwt_token");
    localStorage.removeItem("user_name");
    setToken(null);
    setUserName("Demo Student");
    window.location.reload();
  };

  const saveSettings = () => {
    localStorage.setItem("llm_base_url", apiBaseUrl);
    localStorage.setItem("llm_api_key", apiKey);
    localStorage.setItem("llm_model", apiModel);
    setShowSettingsModal(false);
  };

  const handleTestConnection = async () => {
    setTestStatus({ type: "loading", msg: "Testing connection..." });
    try {
      const res = await fetch(`${API_BASE}/ai/test`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-LLM-Api-Key": apiKey,
          "X-LLM-Base-Url": apiBaseUrl,
          "X-LLM-Model": apiModel,
        }
      });
      const data = await res.json();
      if (data.status === "success") {
        setTestStatus({ type: "success", msg: data.message });
      } else {
        setTestStatus({ type: "error", msg: data.message });
      }
    } catch (err) {
      setTestStatus({ type: "error", msg: "Failed to reach the backend server." });
    }
  };

  const submitSchedule = async (
    payload: { title: string; type: string; start_time: string; end_time: string },
    force = false
  ) => {
    const res = await fetch(`${API_BASE}/schedules`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ ...payload, force }),
    });

    if (res.status === 409) {
      const alertData: ConflictAlert = await res.json();
      setConflict(alertData);
      setPendingEvent(payload);
      return;
    }

    if (res.ok) {
      setConflict(null);
      setPendingEvent(null);
      setParsedPreview(null);
      setTitle("");
      refreshAll();
    }
  };

  const handleNLPSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!nlpInput.trim()) return;
    setNlpLoading(true);
    try {
      const res = await fetch(`${API_BASE}/ai/parse`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ prompt: nlpInput }),
      });
      setParsedPreview(await res.json());
    } finally {
      setNlpLoading(false);
    }
  };

  const handleEventDrop = async (info: any) => {
    const start_time = toLocal(info.event.start);
    const end_time = info.event.end
      ? toLocal(info.event.end)
      : toLocal(new Date(info.event.start.getTime() + 3600000));

    const res = await fetch(`${API_BASE}/schedules/${info.event.id}`, {
      method: "PATCH",
      headers: authHeaders(),
      body: JSON.stringify({ start_time, end_time, force: false }),
    });

    if (res.status === 409) {
      setConflict(await res.json());
      setPendingEvent({
        title: info.event.title.replace(/^\[.*?\]\s*/, ""),
        type: "study",
        start_time,
        end_time,
      });
      info.revert();
    } else {
      refreshAll();
    }
  };

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!taskTitle || !taskDeadline) return;
    const res = await fetch(`${API_BASE}/tasks`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        title: taskTitle,
        description: taskDesc,
        priority: taskPriority,
        estimated_hours: Number(taskHours),
        deadline: taskDeadline,
      }),
    });
    if (res.ok) {
      setTaskTitle("");
      setTaskDesc("");
      refreshAll();
    }
  };

  const handleGenerateStudyPlan = async (taskId: string) => {
    setGeneratingTaskId(taskId);
    try {
      const res = await fetch(`${API_BASE}/study-plans/generate`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ task_id: taskId }),
      });
      if (res.ok) {
        await refreshAll();
      } else {
        alert("Failed to generate plan. Check if your API key is correct in the AI Settings.");
      }
    } finally {
      setGeneratingTaskId(null);
    }
  };

  const handleToggleSession = async (sessionId: string) => {
    await fetch(`${API_BASE}/study-sessions/${sessionId}/toggle`, {
      method: "PATCH",
      headers: authHeaders(),
    });
    refreshAll();
  };

  const handleBalanceWorkload = async () => {
    const res = await fetch(`${API_BASE}/workload/balance`, {
      method: "POST",
      headers: authHeaders(),
    });
    if (res.ok) {
      const data = await res.json();
      setDailyLoad(data.daily_summary);
      setBalanceLogs(data.details);
      refreshAll();
    }
  };

  const handleCreateSemester = async () => {
    await fetch(`${API_BASE}/semester-plans`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ semester_start: semStart, semester_end: semEnd }),
    });
    refreshAll();
  };

  const handleAddSemesterEvent = async (planId: string) => {
    if (!semEventTitle || !semEventDate) return;
    await fetch(`${API_BASE}/semester-events`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        semester_plan_id: planId,
        title: semEventTitle,
        type: semEventType,
        date: semEventDate,
      }),
    });
    setSemEventTitle("");
    refreshAll();
  };

  const handleDeleteSemesterEvent = async (eventId: string) => {
    if (!window.confirm("Are you sure you want to delete this milestone?")) return;
    await fetch(`${API_BASE}/semester-events/${eventId}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    refreshAll();
  };

  const handleDeleteSemesterPlan = async (planId: string) => {
    if (!window.confirm("Are you sure you want to delete this ENTIRE semester plan?")) return;
    await fetch(`${API_BASE}/semester-plans/${planId}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    refreshAll();
  };

  const handleDistributeSemester = async (planId: string) => {
    setSemStatusMsg("Generating & scheduling early study blocks with AI...");
    const res = await fetch(`${API_BASE}/semester-plans/${planId}/distribute`, {
      method: "POST",
      headers: authHeaders(),
    });
    if (res.ok) {
      const data = await res.json();
      setSemStatusMsg(data.message);
      refreshAll();
    }
  };

  const calendarEvents = schedules.map((s) => ({
    id: s.id,
    title: `[${s.type.toUpperCase()}] ${s.title}`,
    start: s.start_time,
    end: s.end_time,
    backgroundColor: TYPE_COLORS[s.type] || "#2563eb",
    borderColor: TYPE_COLORS[s.type] || "#2563eb",
  }));

  return (
    // Balanced padding and max-width
    <div style={{ fontFamily: "system-ui, sans-serif", padding: "24px", maxWidth: "1400px", margin: "0 auto", color: "#0f172a" }}>
      
      {/* Top Header & Navigation */}
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "24px",
          borderBottom: "1px solid #e5e7eb",
          paddingBottom: "16px",
        }}
      >
        <div>
          <h1 style={{ margin: 0, fontSize: "24px", color: "#0f172a" }}>
            Web-Based AI-Assisted Schedule Management System
          </h1>
          <p style={{ margin: "6px 0 0", color: "#64748b", fontSize: "14px" }}>
            Signed in as <strong style={{ color: "#0f172a" }}>{userName}</strong> | LLM-Agnostic Engine (Ollama / Cloud API)
          </p>
        </div>

        <div style={{ display: "flex", gap: "10px" }}>
          {(["calendar", "study", "workload", "semester"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                padding: "10px 16px",
                borderRadius: "6px",
                border: "1px solid #cbd5e1",
                background: activeTab === tab ? "#0f172a" : "#ffffff",
                color: activeTab === tab ? "#ffffff" : "#0f172a",
                cursor: "pointer",
                fontWeight: 600,
                fontSize: "14px",
                textTransform: "capitalize",
              }}
            >
              {tab === "calendar" && "Interactive Calendar"}
              {tab === "study" && "Smart Study Planner"}
              {tab === "workload" && "Workload Balancer"}
              {tab === "semester" && "Semester Planner"}
            </button>
          ))}
          
          <button
            onClick={() => setShowSettingsModal(true)}
            style={{
              padding: "10px 16px",
              borderRadius: "6px",
              border: "1px solid #16a34a",
              background: "#dcfce7",
              color: "#166534",
              cursor: "pointer",
              fontWeight: 600,
              fontSize: "14px",
            }}
          >
            AI Settings
          </button>

          {token ? (
            <button
              onClick={handleLogout}
              style={{
                padding: "10px 16px",
                borderRadius: "6px",
                border: "1px solid #dc2626",
                background: "#fee2e2",
                color: "#991b1b",
                cursor: "pointer",
                fontWeight: 600,
                fontSize: "14px",
              }}
            >
              Logout
            </button>
          ) : (
            <button
              onClick={() => setShowAuthModal(true)}
              style={{
                padding: "10px 16px",
                borderRadius: "6px",
                border: "1px solid #2563eb",
                background: "#eff6ff",
                color: "#1d4ed8",
                cursor: "pointer",
                fontWeight: 600,
                fontSize: "14px",
              }}
            >
              JWT Account
            </button>
          )}
        </div>
      </header>

      {/* AI Settings Modal */}
      {showSettingsModal && (
        <div style={{ background: "#f8fafc", border: "2px solid #16a34a", padding: "24px", borderRadius: "8px", marginBottom: "24px" }}>
          <h3 style={{ marginTop: 0, fontSize: "20px", color: "#166534" }}>Custom AI API Settings</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "12px", maxWidth: "600px" }}>
            
            <label style={{ fontSize: "14px", fontWeight: 600, color: "#0f172a" }}>API Base URL</label>
            <input type="text" value={apiBaseUrl} onChange={(e) => setApiBaseUrl(e.target.value)} placeholder="e.g., https://openrouter.ai/api/v1" style={inputStyle} />
            
            <label style={{ fontSize: "14px", fontWeight: 600, color: "#0f172a" }}>API Key</label>
            <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="sk-..." style={inputStyle} />
            
            <label style={{ fontSize: "14px", fontWeight: 600, color: "#0f172a" }}>Model Name</label>
            <input type="text" value={apiModel} onChange={(e) => setApiModel(e.target.value)} placeholder="e.g., google/gemini-2.0-flash-exp:free" style={inputStyle} />
            
            <div style={{ display: "flex", gap: "10px", marginTop: "12px", alignItems: "center" }}>
              <button onClick={saveSettings} style={{ background: "#16a34a", color: "white", padding: "10px 20px", borderRadius: "6px", border: "none", cursor: "pointer", fontWeight: 600, fontSize: "14px" }}>Save Settings</button>
              
              <button onClick={handleTestConnection} disabled={testStatus?.type === "loading"} style={{ background: "#2563eb", color: "white", padding: "10px 20px", borderRadius: "6px", border: "none", cursor: "pointer", fontWeight: 600, fontSize: "14px" }}>
                {testStatus?.type === "loading" ? "Testing..." : "Test Connection"}
              </button>

              <button onClick={() => setShowSettingsModal(false)} style={{ background: "#e2e8f0", color: "#0f172a", padding: "10px 20px", borderRadius: "6px", border: "none", cursor: "pointer", fontSize: "14px" }}>Close</button>
            </div>

            {testStatus && (
              <div style={{ 
                marginTop: "12px", 
                padding: "12px", 
                borderRadius: "6px", 
                background: testStatus.type === "success" ? "#dcfce7" : testStatus.type === "error" ? "#fee2e2" : "#eff6ff",
                color: testStatus.type === "success" ? "#166534" : testStatus.type === "error" ? "#991b1b" : "#1e3a8a",
                border: `1px solid ${testStatus.type === "success" ? "#16a34a" : testStatus.type === "error" ? "#dc2626" : "#3b82f6"}`,
                fontSize: "14px"
              }}>
                <strong>{testStatus.type === "success" ? "✅ " : testStatus.type === "error" ? "❌ " : "⏳ "}</strong>
                {testStatus.msg}
              </div>
            )}
          </div>
        </div>
      )}

      {/* JWT Auth Modal */}
      {showAuthModal && (
        <div style={{ background: "#f8fafc", border: "1px solid #94a3b8", padding: "24px", borderRadius: "8px", marginBottom: "24px" }}>
          <h3 style={{ marginTop: 0, fontSize: "20px", color: "#0f172a" }}>{isRegister ? "Register New Account" : "Sign In with JWT"}</h3>
          <form onSubmit={handleAuthSubmit} style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
            {isRegister && (
              <input type="text" placeholder="Full Name" value={authName} onChange={(e) => setAuthName(e.target.value)} required style={{ ...inputStyle, maxWidth: "280px" }} />
            )}
            <input type="email" placeholder="Email" value={authEmail} onChange={(e) => setAuthEmail(e.target.value)} required style={{ ...inputStyle, maxWidth: "280px" }} />
            <input type="password" placeholder="Password" value={authPassword} onChange={(e) => setAuthPassword(e.target.value)} required style={{ ...inputStyle, maxWidth: "280px" }} />
            <button type="submit" style={{ background: "#2563eb", color: "white", padding: "10px 20px", borderRadius: "6px", border: "none", cursor: "pointer", fontWeight: 600, fontSize: "14px" }}>{isRegister ? "Register" : "Login"}</button>
            <button type="button" onClick={() => setIsRegister(!isRegister)} style={{ background: "transparent", border: "none", color: "#2563eb", cursor: "pointer", fontWeight: 600, fontSize: "14px" }}>{isRegister ? "Already have an account? Login" : "Need an account? Register"}</button>
            <button type="button" onClick={() => setShowAuthModal(false)} style={{ background: "#e2e8f0", padding: "10px 16px", borderRadius: "6px", border: "none", cursor: "pointer", color: "#0f172a", fontSize: "14px" }}>Close</button>
          </form>
        </div>
      )}

      {/* Natural Language Input Bar */}
      <form onSubmit={handleNLPSubmit} style={{ display: "flex", gap: "12px", background: "#f8fafc", padding: "16px", borderRadius: "8px", border: "1px solid #cbd5e1", marginBottom: "24px" }}>
        <input type="text" value={nlpInput} onChange={(e) => setNlpInput(e.target.value)} placeholder='Natural Language Command: e.g., "Schedule a 2-hour study block before Friday exam at 14:00"' style={{ ...inputStyle, flex: 1, fontSize: "15px" }} />
        <button type="submit" disabled={nlpLoading} style={{ background: "#0f172a", color: "white", padding: "10px 20px", borderRadius: "6px", border: "none", cursor: "pointer", fontWeight: 600, fontSize: "15px" }}>{nlpLoading ? "Parsing..." : "AI Parse Command"}</button>
      </form>

      {parsedPreview && (
        <div style={{ background: "#eff6ff", border: "1px solid #60a5fa", padding: "16px", borderRadius: "8px", marginBottom: "24px", display: "flex", justifyContent: "space-between", alignItems: "center", color: "#1e3a8a", fontSize: "15px" }}>
          <div>
            <strong>AI Extracted:</strong> {parsedPreview.title} ({parsedPreview.event_type.toUpperCase()}) |{" "}{parsedPreview.start_time.replace("T", " ")} → {parsedPreview.end_time.replace("T", " ")}
          </div>
          <div style={{ display: "flex", gap: "10px" }}>
            <button onClick={() => submitSchedule({ title: parsedPreview.title, type: parsedPreview.event_type, start_time: parsedPreview.start_time, end_time: parsedPreview.end_time })} style={{ background: "#16a34a", color: "white", padding: "8px 16px", borderRadius: "6px", border: "none", cursor: "pointer", fontSize: "14px", fontWeight: 600 }}>Confirm & Schedule</button>
            <button onClick={() => setParsedPreview(null)} style={{ background: "#e2e8f0", padding: "8px 16px", borderRadius: "6px", border: "none", cursor: "pointer", color: "#0f172a", fontSize: "14px" }}>Cancel</button>
          </div>
        </div>
      )}

      {conflict && (
        <div style={{ background: "#fef2f2", border: "2px solid #ef4444", padding: "20px", borderRadius: "8px", marginBottom: "24px" }}>
          <h3 style={{ margin: "0 0 10px", color: "#b91c1c", fontSize: "18px" }}>Conflict Detection Engine Alert</h3>
          <p style={{ margin: "0 0 12px", color: "#7f1d1d", fontSize: "15px" }}>{conflict.message}</p>
          {pendingEvent && conflict.suggested_resolutions.length > 0 && (
            <div style={{ marginBottom: "12px" }}>
              <strong style={{ color: "#7f1d1d", fontSize: "14px" }}>Suggested Conflict-Free Slots:</strong>
              <div style={{ display: "flex", gap: "10px", marginTop: "10px", flexWrap: "wrap" }}>
                {conflict.suggested_resolutions.map((slot, idx) => (
                  <button key={idx} onClick={() => submitSchedule({ ...pendingEvent, start_time: slot.start_time, end_time: slot.end_time })} style={{ background: "#ffffff", border: "1px solid #16a34a", color: "#15803d", padding: "8px 14px", borderRadius: "6px", cursor: "pointer", fontWeight: 600, fontSize: "14px" }}>Move to {slot.label}</button>
                ))}
              </div>
            </div>
          )}
          <div style={{ display: "flex", gap: "10px" }}>
            {pendingEvent && (
              <button onClick={() => submitSchedule(pendingEvent, true)} style={{ background: "#dc2626", color: "white", padding: "8px 14px", borderRadius: "6px", border: "none", cursor: "pointer", fontSize: "14px" }}>Force Overlap Anyway</button>
            )}
            <button onClick={() => setConflict(null)} style={{ background: "#e5e7eb", padding: "8px 14px", borderRadius: "6px", border: "none", cursor: "pointer", color: "#0f172a", fontSize: "14px" }}>Dismiss</button>
          </div>
        </div>
      )}

      {/* ==================== TAB 1: INTERACTIVE CALENDAR ==================== */}
      {activeTab === "calendar" && (
        <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: "24px" }}>
          <div style={{ background: "#f9fafb", padding: "20px", borderRadius: "8px", border: "1px solid #e5e7eb", height: "fit-content" }}>
            <h3 style={{ marginTop: 0, fontSize: "18px", color: "#0f172a", marginBottom: "16px" }}>Add Schedule Event</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <input type="text" placeholder="Title (e.g., Operating Systems Lecture)" value={title} onChange={(e) => setTitle(e.target.value)} style={inputStyle} />
              <select value={type} onChange={(e) => setType(e.target.value as any)} style={inputStyle}>
                <option value="study">Study Session (Green)</option>
                <option value="class">Class (Blue)</option>
                <option value="exam">Exam (Red)</option>
                <option value="event">Event (Purple)</option>
              </select>
              <label style={{ fontSize: "13px", fontWeight: 600, color: "#0f172a" }}>Start Time</label>
              <input type="datetime-local" value={startTime} onChange={(e) => setStartTime(e.target.value)} style={inputStyle} />
              <label style={{ fontSize: "13px", fontWeight: 600, color: "#0f172a" }}>End Time</label>
              <input type="datetime-local" value={endTime} onChange={(e) => setEndTime(e.target.value)} style={inputStyle} />
              <button onClick={() => { if (title && startTime && endTime) submitSchedule({ title, type, start_time: startTime, end_time: endTime }); }} style={{ background: "#2563eb", color: "white", padding: "12px", borderRadius: "6px", border: "none", cursor: "pointer", fontWeight: 600, fontSize: "15px", marginTop: "8px" }}>Add to Calendar</button>
            </div>
          </div>

          <div>
            <FullCalendar plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]} initialView="timeGridWeek" headerToolbar={{ left: "prev,next today", center: "title", right: "timeGridWeek,dayGridMonth" }} editable={true} eventDrop={handleEventDrop} events={calendarEvents} slotMinTime="07:00:00" slotMaxTime="23:00:00" allDaySlot={false} height="750px" eventClick={(info) => { if (window.confirm(`Delete '${info.event.title}'?`)) { fetch(`${API_BASE}/schedules/${info.event.id}`, { method: "DELETE", headers: authHeaders() }).then(() => refreshAll()); } }} />
          </div>
        </div>
      )}

      {/* ==================== TAB 2: TASKS & SMART STUDY PLANNER ==================== */}
      {activeTab === "study" && (
        <div style={{ display: "grid", gridTemplateColumns: "360px 1fr", gap: "24px" }}>
          <form onSubmit={handleCreateTask} style={{ background: "#f9fafb", padding: "20px", borderRadius: "8px", border: "1px solid #e5e7eb", height: "fit-content" }}>
            <h3 style={{ marginTop: 0, fontSize: "18px", color: "#0f172a", marginBottom: "16px" }}>Create Exam / Study Task</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <input type="text" placeholder="Exam or Task Title (e.g., Database Systems Final)" value={taskTitle} onChange={(e) => setTaskTitle(e.target.value)} required style={inputStyle} />
              <textarea placeholder="Syllabus topics or description" value={taskDesc} onChange={(e) => setTaskDesc(e.target.value)} rows={3} style={{ ...inputStyle, resize: "vertical" }} />
              <label style={{ fontSize: "13px", fontWeight: 600, color: "#0f172a" }}>Priority</label>
              <select value={taskPriority} onChange={(e) => setTaskPriority(e.target.value as any)} style={inputStyle}>
                <option value="high">High Priority</option>
                <option value="medium">Medium Priority</option>
                <option value="low">Low Priority</option>
              </select>
              <label style={{ fontSize: "13px", fontWeight: 600, color: "#0f172a" }}>Estimated Study Hours</label>
              <input type="number" min={1} max={40} value={taskHours} onChange={(e) => setTaskHours(Number(e.target.value))} style={inputStyle} />
              <label style={{ fontSize: "13px", fontWeight: 600, color: "#0f172a" }}>Exam / Task Deadline</label>
              <input type="datetime-local" value={taskDeadline} onChange={(e) => setTaskDeadline(e.target.value)} required style={inputStyle} />
              <button type="submit" style={{ background: "#0f172a", color: "white", padding: "12px", borderRadius: "6px", border: "none", cursor: "pointer", fontWeight: 600, fontSize: "15px", marginTop: "8px" }}>Save Task</button>
            </div>
          </form>

          <div>
            <h3 style={{ marginTop: 0, fontSize: "20px", color: "#0f172a", marginBottom: "16px" }}>Your Tasks & AI Smart Study Session Generator</h3>
            {tasks.length === 0 ? (
              <p style={{ color: "#64748b", fontSize: "15px" }}>No tasks yet. Create an exam or study task on the left to generate an AI study plan.</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginBottom: "32px" }}>
                {tasks.map((t) => (
                  <div key={t.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "16px", borderRadius: "8px", border: "1px solid #cbd5e1", background: "#ffffff" }}>
                    <div>
                      <strong style={{ color: "#0f172a", fontSize: "16px" }}>{t.title}</strong> <span style={{ fontSize: "15px" }}>({t.priority.toUpperCase()}) — {t.estimated_hours} hrs | Deadline:{" "}{t.deadline.replace("T", " ")}</span>
                      {t.description && <div style={{ fontSize: "14px", color: "#475569", marginTop: "6px" }}>{t.description}</div>}
                    </div>
                    <div style={{ display: "flex", gap: "10px" }}>
                      <button onClick={() => handleGenerateStudyPlan(t.id)} disabled={generatingTaskId === t.id} style={{ background: "#16a34a", color: "white", padding: "10px 16px", borderRadius: "6px", border: "none", cursor: "pointer", fontWeight: 600, fontSize: "14px" }}>{generatingTaskId === t.id ? "AI Generating Subtopics & Slots..." : "Generate Smart Study Plan"}</button>
                      <button onClick={() => fetch(`${API_BASE}/tasks/${t.id}`, { method: "DELETE", headers: authHeaders() }).then(() => refreshAll())} style={{ background: "#fee2e2", color: "#991b1b", padding: "10px 16px", borderRadius: "6px", border: "none", cursor: "pointer", fontSize: "14px", fontWeight: 600 }}>Delete</button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <h3 style={{ fontSize: "20px", color: "#0f172a", marginBottom: "16px" }}>Generated Study Plans & Auto-Scheduled Sessions</h3>
            {studyPlans.map((plan) => (
              <div key={plan.id} style={{ background: "#f8fafc", border: "1px solid #94a3b8", borderRadius: "8px", padding: "20px", marginBottom: "20px" }}>
                <h4 style={{ margin: "0 0 12px", fontSize: "16px", color: "#0f172a" }}>Study Plan for: {plan.task_title} ({plan.sessions.length} Auto-Scheduled Sessions)</h4>
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {plan.sessions.map((sess) => (
                    <div key={sess.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: sess.completed ? "#dcfce7" : "#ffffff", padding: "12px 16px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "15px" }}>
                      <div style={{ color: "#0f172a" }}>
                        <span style={{ textDecoration: sess.completed ? "line-through" : "none", fontWeight: 600 }}>{sess.topic}</span>{" "}({sess.duration_minutes} mins) — Scheduled: {sess.scheduled_start.replace("T", " ")}
                      </div>
                      <button onClick={() => handleToggleSession(sess.id)} style={{ background: sess.completed ? "#15803d" : "#e2e8f0", color: sess.completed ? "white" : "#0f172a", padding: "8px 14px", borderRadius: "4px", border: "none", cursor: "pointer", fontWeight: 600, fontSize: "13px" }}>{sess.completed ? "Completed ✓" : "Mark Complete"}</button>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ==================== TAB 3: WORKLOAD BALANCING MODULE ==================== */}
      {activeTab === "workload" && (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px" }}>
            <div>
              <h2 style={{ margin: 0, fontSize: "24px", color: "#0f172a" }}>Weekly Workload Balancing Module</h2>
              <p style={{ margin: "6px 0 0", color: "#475569", fontSize: "15px" }}>Analyzes daily task density across the next 7 days and redistributes flexible study/event blocks from overloaded days (&gt;5 hrs).</p>
            </div>
            <button onClick={handleBalanceWorkload} style={{ background: "#2563eb", color: "white", padding: "12px 24px", borderRadius: "6px", border: "none", cursor: "pointer", fontWeight: 600, fontSize: "15px" }}>Auto-Balance Weekly Workload</button>
          </div>

          {balanceLogs.length > 0 && (
            <div style={{ background: "#eff6ff", border: "1px solid #60a5fa", padding: "20px", borderRadius: "8px", marginBottom: "24px", color: "#1e3a8a", fontSize: "15px" }}>
              <strong style={{ fontSize: "16px" }}>Workload Redistribution Log:</strong>
              <ul style={{ margin: "10px 0 0", paddingLeft: "20px" }}>
                {balanceLogs.map((log, i) => (<li key={i} style={{ marginBottom: "6px" }}>{log}</li>))}
              </ul>
            </div>
          )}

          <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: "16px" }}>
            {dailyLoad.map((day, idx) => (
              <div key={idx} style={{ padding: "20px 16px", borderRadius: "8px", border: day.overloaded ? "2px solid #dc2626" : "1px solid #cbd5e1", background: day.overloaded ? "#fef2f2" : "#f8fafc" }}>
                <div style={{ fontWeight: 700, marginBottom: "10px", color: "#0f172a", fontSize: "15px" }}>{day.date}</div>
                <div style={{ fontSize: "28px", fontWeight: 800, color: day.overloaded ? "#dc2626" : "#0f172a" }}>{day.total_hours} hrs</div>
                <div style={{ fontSize: "14px", color: "#475569", marginTop: "6px" }}>{day.event_count} scheduled items</div>
                {day.overloaded && (<div style={{ marginTop: "10px", fontSize: "13px", fontWeight: 700, color: "#b91c1c" }}>OVERLOADED (&gt;5h)</div>)}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ==================== TAB 4: SEMESTER PLANNER ==================== */}
      {activeTab === "semester" && (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px" }}>
            <div>
              <h2 style={{ margin: 0, fontSize: "24px", color: "#0f172a" }}>Macro-Level Semester Planner</h2>
              <p style={{ margin: "6px 0 0", color: "#475569", fontSize: "15px" }}>Identifies high-risk weeks with overlapping exams/deadlines and pre-emptively distributes preparatory study sessions.</p>
            </div>
            {semesterPlans.length === 0 && (
              <button onClick={handleCreateSemester} style={{ background: "#0f172a", color: "white", padding: "12px 24px", borderRadius: "6px", border: "none", cursor: "pointer", fontWeight: 600, fontSize: "15px" }}>Initialize Fall/Spring Semester Plan</button>
            )}
          </div>

          {semStatusMsg && (<div style={{ background: "#dcfce7", border: "1px solid #16a34a", padding: "16px", borderRadius: "8px", marginBottom: "20px", color: "#166534", fontSize: "15px", fontWeight: 600 }}>{semStatusMsg}</div>)}

          {semesterPlans.map((sp) => (
            <div key={sp.id} style={{ background: "#f8fafc", border: "1px solid #cbd5e1", borderRadius: "8px", padding: "24px", marginBottom: "24px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
                <h3 style={{ margin: 0, fontSize: "20px", color: "#0f172a" }}>Semester Window: {sp.semester_start.slice(0, 10)} → {sp.semester_end.slice(0, 10)}</h3>
                <div style={{ display: "flex", gap: "12px" }}>
                  <button onClick={() => handleDistributeSemester(sp.id)} style={{ background: "#16a34a", color: "white", padding: "12px 20px", borderRadius: "6px", border: "none", cursor: "pointer", fontWeight: 600, fontSize: "15px" }}>Pre-Emptively Distribute Study Load into Calendar</button>
                  <button onClick={() => handleDeleteSemesterPlan(sp.id)} style={{ background: "#fee2e2", color: "#991b1b", padding: "12px 20px", borderRadius: "6px", border: "none", cursor: "pointer", fontWeight: 600, fontSize: "15px" }}>Delete Plan</button>
                </div>
              </div>

              {sp.high_risk_weeks.length > 0 && (
                <div style={{ background: "#fef2f2", border: "1px solid #ef4444", padding: "16px", borderRadius: "6px", marginBottom: "20px" }}>
                  <strong style={{ color: "#b91c1c", display: "block", marginBottom: "6px", fontSize: "16px" }}>High-Risk Overlapping Deadline Periods Detected:</strong>
                  <div style={{ color: "#7f1d1d", fontSize: "15px", paddingLeft: "8px" }}>
                    {sp.high_risk_weeks.map((w, i) => (<div key={i} style={{ marginTop: "4px" }}>⚠️ {w}</div>))}
                  </div>
                </div>
              )}

              <div style={{ display: "flex", gap: "12px", marginBottom: "20px", alignItems: "center", flexWrap: "wrap" }}>
                <input type="text" placeholder="Milestone (e.g., Algorithms Midterm)" value={semEventTitle} onChange={(e) => setSemEventTitle(e.target.value)} style={{ ...inputStyle, flex: "1 1 250px" }} />
                <select value={semEventType} onChange={(e) => setSemEventType(e.target.value)} style={{ ...inputStyle, flex: "0 0 160px" }}>
                  <option value="exam">Final Exam</option>
                  <option value="midterm">Midterm</option>
                  <option value="project">Project Deadline</option>
                </select>
                <input type="datetime-local" value={semEventDate} onChange={(e) => setSemEventDate(e.target.value)} style={{ ...inputStyle, flex: "0 0 200px" }} />
                <button onClick={() => handleAddSemesterEvent(sp.id)} style={{ background: "#2563eb", color: "white", padding: "10px 20px", borderRadius: "6px", border: "none", cursor: "pointer", flex: "0 0 auto", fontSize: "15px", fontWeight: 600 }}>Add Milestone</button>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                {sp.events.map((ev) => (
                  <div key={ev.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", borderRadius: "6px", background: "#ffffff", border: ev.risk_level === "high" ? "2px solid #dc2626" : "1px solid #cbd5e1", fontSize: "15px" }}>
                    <div style={{ color: "#0f172a", display: "flex", alignItems: "center", gap: "12px" }}>
                      <strong>{ev.title}</strong> <span>({ev.type.toUpperCase()}) — {ev.date.replace("T", " ")}</span>
                      <span style={{ padding: "2px 10px", borderRadius: "999px", fontSize: "12px", fontWeight: 700, background: ev.risk_level === "high" ? "#fee2e2" : ev.risk_level === "medium" ? "#fef3c7" : "#dcfce7", color: ev.risk_level === "high" ? "#991b1b" : ev.risk_level === "medium" ? "#92400e" : "#166534" }}>RISK: {ev.risk_level.toUpperCase()}</span>
                    </div>
                    <button onClick={() => handleDeleteSemesterEvent(ev.id)} style={{ background: "#fee2e2", color: "#991b1b", padding: "6px 12px", borderRadius: "4px", border: "none", cursor: "pointer", fontSize: "13px", fontWeight: 600 }}>Delete</button>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}