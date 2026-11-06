import React, { useEffect, useState } from "react";
import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid";
import timeGridPlugin from "@fullcalendar/timegrid";
import interactionPlugin from "@fullcalendar/interaction";
import type { ScheduleItem, ConflictAlert, NLPParsedOutput } from "./api";

const API_BASE = "http://localhost:8000/api";

const TYPE_COLORS: Record<string, string> = {
  class: "#2563eb", // Blue
  exam: "#dc2626",  // Red
  study: "#16a34a", // Green
  event: "#7c3aed", // Purple
};

export default function App() {
  const [schedules, setSchedules] = useState<ScheduleItem[]>([]);
  const [nlpInput, setNlpInput] = useState("");
  const [nlpLoading, setNlpLoading] = useState(false);
  const [parsedPreview, setParsedPreview] = useState<NLPParsedOutput | null>(null);

  // Conflict state + pending payload for 1-click resolution
  const [conflict, setConflict] = useState<ConflictAlert | null>(null);
  const [pendingEvent, setPendingEvent] = useState<{
    title: string;
    type: string;
    start_time: string;
    end_time: string;
  } | null>(null);

  // Manual form state
  const [title, setTitle] = useState("");
  const [type, setType] = useState<"class" | "exam" | "event" | "study">("study");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");

  const fetchSchedules = async () => {
    const res = await fetch(`${API_BASE}/schedules`);
    const data = await res.json();
    setSchedules(data);
  };

  useEffect(() => {
    fetchSchedules();
  }, []);

  const submitSchedule = async (
    payload: { title: string; type: string; start_time: string; end_time: string },
    force = false
  ) => {
    const res = await fetch(`${API_BASE}/schedules`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
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
      fetchSchedules();
    }
  };

  const handleNLPSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!nlpInput.trim()) return;
    setNlpLoading(true);
    try {
      const res = await fetch(`${API_BASE}/ai/parse`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: nlpInput }),
      });
      const data: NLPParsedOutput = await res.json();
      setParsedPreview(data);
    } finally {
      setNlpLoading(false);
    }
  };

  const handleEventDrop = async (info: any) => {
    const start_time = info.event.start.toISOString();
    const end_time = info.event.end
      ? info.event.end.toISOString()
      : new Date(info.event.start.getTime() + 3600000).toISOString();

    const res = await fetch(`${API_BASE}/schedules/${info.event.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ start_time, end_time, force: false }),
    });

    if (res.status === 409) {
      const alertData: ConflictAlert = await res.json();
      setConflict(alertData);
      info.revert();
    } else {
      fetchSchedules();
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
    <div style={{ fontFamily: "system-ui, sans-serif", padding: "24px", maxWidth: "1400px", margin: "0 auto" }}>
      <header style={{ marginBottom: "20px", borderBottom: "1px solid #e5e7eb", paddingBottom: "16px" }}>
        <h1 style={{ margin: 0, fontSize: "24px", color: "#0f172a" }}>
          AI-Assisted Schedule Management System (Tier 1 Core)
        </h1>
        <p style={{ margin: "4px 0 0", color: "#6b7280", fontSize: "14px" }}>
          FastAPI + PostgreSQL + Deterministic Conflict Engine + Ollama NLP Parser
        </p>
      </header>

      {/* Natural Language Input Bar */}
      <form
        onSubmit={handleNLPSubmit}
        style={{
          display: "flex",
          gap: "12px",
          background: "#f8fafc",
          padding: "16px",
          borderRadius: "8px",
          border: "1px solid #cbd5e1",
          marginBottom: "20px",
        }}
      >
        <input
          type="text"
          value={nlpInput}
          onChange={(e) => setNlpInput(e.target.value)}
          placeholder='Ask AI in plain English: e.g., "Schedule a 2-hour Operating Systems study block tomorrow at 14:00"'
          style={{ flex: 1, padding: "10px 14px", borderRadius: "6px", border: "1px solid #94a3b8", fontSize: "15px" }}
        />
        <button
          type="submit"
          disabled={nlpLoading}
          style={{
            background: "#0f172a",
            color: "white",
            padding: "10px 20px",
            borderRadius: "6px",
            border: "none",
            cursor: "pointer",
            fontWeight: 600,
          }}
        >
          {nlpLoading ? "Parsing with Ollama..." : "AI Parse Command"}
        </button>
      </form>

      {/* AI Parsed Preview Banner */}
      {parsedPreview && (
        <div
          style={{
            background: "#eff6ff",
            border: "1px solid #60a5fa",
            padding: "16px",
            borderRadius: "8px",
            marginBottom: "20px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div>
            <strong>AI Extracted Event:</strong> {parsedPreview.title} ({parsedPreview.event_type.toUpperCase()}) |{" "}
            <span>
              {parsedPreview.start_time.replace("T", " ")} → {parsedPreview.end_time.replace("T", " ")}
            </span>
          </div>
          <div style={{ display: "flex", gap: "8px" }}>
            <button
              onClick={() =>
                submitSchedule({
                  title: parsedPreview.title,
                  type: parsedPreview.event_type,
                  start_time: parsedPreview.start_time,
                  end_time: parsedPreview.end_time,
                })
              }
              style={{ background: "#16a34a", color: "white", padding: "8px 14px", borderRadius: "6px", border: "none", cursor: "pointer" }}
            >
              Confirm & Add to Calendar
            </button>
            <button
              onClick={() => setParsedPreview(null)}
              style={{ background: "#e2e8f0", padding: "8px 14px", borderRadius: "6px", border: "none", cursor: "pointer" }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Deterministic Conflict Resolution Banner */}
      {conflict && (
        <div
          style={{
            background: "#fef2f2",
            border: "2px solid #ef4444",
            padding: "16px",
            borderRadius: "8px",
            marginBottom: "20px",
          }}
        >
          <h3 style={{ margin: "0 0 8px", color: "#b91c1c" }}>⚠️ Schedule Conflict Detected</h3>
          <p style={{ margin: "0 0 12px" }}>{conflict.message}</p>

          {pendingEvent && conflict.suggested_resolutions.length > 0 && (
            <div style={{ marginBottom: "12px" }}>
              <strong>Suggested Conflict-Free Slots (1-Click Auto-Resolve):</strong>
              <div style={{ display: "flex", gap: "8px", marginTop: "8px", flexWrap: "wrap" }}>
                {conflict.suggested_resolutions.map((slot, idx) => (
                  <button
                    key={idx}
                    onClick={() =>
                      submitSchedule({
                        ...pendingEvent,
                        start_time: slot.start_time,
                        end_time: slot.end_time,
                      })
                    }
                    style={{
                      background: "#ffffff",
                      border: "1px solid #16a34a",
                      color: "#15803d",
                      padding: "6px 12px",
                      borderRadius: "6px",
                      cursor: "pointer",
                      fontWeight: 600,
                    }}
                  >
                    Schedule at {slot.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div style={{ display: "flex", gap: "8px" }}>
            {pendingEvent && (
              <button
                onClick={() => submitSchedule(pendingEvent, true)}
                style={{ background: "#dc2626", color: "white", padding: "6px 12px", borderRadius: "6px", border: "none", cursor: "pointer" }}
              >
                Force Overlap Anyway
              </button>
            )}
            <button
              onClick={() => setConflict(null)}
              style={{ background: "#e5e7eb", padding: "6px 12px", borderRadius: "6px", border: "none", cursor: "pointer" }}
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: "24px" }}>
        {/* Left Sidebar: Manual Quick-Add */}
        <div style={{ background: "#f9fafb", padding: "16px", borderRadius: "8px", border: "1px solid #e5e7eb", height: "fit-content" }}>
          <h3 style={{ marginTop: 0 }}>Add Schedule Item</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            <input
              type="text"
              placeholder="Title (e.g., Algorithms Exam)"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              style={{ padding: "8px", borderRadius: "4px", border: "1px solid #d1d5db" }}
            />
            <select
              value={type}
              onChange={(e) => setType(e.target.value as any)}
              style={{ padding: "8px", borderRadius: "4px", border: "1px solid #d1d5db" }}
            >
              <option value="study">Study Session (Green)</option>
              <option value="class">University Class (Blue)</option>
              <option value="exam">Exam (Red)</option>
              <option value="event">General Event (Purple)</option>
            </select>
            <label style={{ fontSize: "12px", fontWeight: 600 }}>Start Time</label>
            <input
              type="datetime-local"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
              style={{ padding: "8px", borderRadius: "4px", border: "1px solid #d1d5db" }}
            />
            <label style={{ fontSize: "12px", fontWeight: 600 }}>End Time</label>
            <input
              type="datetime-local"
              value={endTime}
              onChange={(e) => setEndTime(e.target.value)}
              style={{ padding: "8px", borderRadius: "4px", border: "1px solid #d1d5db" }}
            />
            <button
              onClick={() => {
                if (title && startTime && endTime) {
                  submitSchedule({ title, type, start_time: startTime, end_time: endTime });
                }
              }}
              style={{
                background: "#2563eb",
                color: "white",
                padding: "10px",
                borderRadius: "6px",
                border: "none",
                cursor: "pointer",
                fontWeight: 600,
                marginTop: "6px",
              }}
            >
              Add to Calendar
            </button>
          </div>
        </div>

        {/* Interactive Weekly/Monthly Calendar with Drag & Drop */}
        <div>
          <FullCalendar
            plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
            initialView="timeGridWeek"
            headerToolbar={{
              left: "prev,next today",
              center: "title",
              right: "timeGridWeek,dayGridMonth",
            }}
            editable={true}
            eventDrop={handleEventDrop}
            events={calendarEvents}
            slotMinTime="07:00:00"
            slotMaxTime="23:00:00"
            allDaySlot={false}
            height="720px"
            eventClick={(info) => {
              if (window.confirm(`Delete '${info.event.title}'?`)) {
                fetch(`${API_BASE}/schedules/${info.event.id}`, { method: "DELETE" }).then(() =>
                  fetchSchedules()
                );
              }
            }}
          />
        </div>
      </div>
    </div>
  );
}