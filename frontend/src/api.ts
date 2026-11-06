const API_BASE = "http://localhost:8000/api";

export interface ScheduleItem {
  id: string;
  title: string;
  type: "class" | "exam" | "event" | "study";
  start_time: string;
  end_time: string;
}

export interface ResolutionSlot {
  start_time: string;
  end_time: string;
  label: string;
}

export interface ConflictAlert {
  message: string;
  conflicting_events: ScheduleItem[];
  suggested_resolutions: ResolutionSlot[];
}

export interface NLPParsedOutput {
  intent_type: string;
  title: string;
  event_type: "class" | "exam" | "event" | "study";
  priority: string;
  start_time: string;
  end_time: string;
  estimated_hours: number;
}