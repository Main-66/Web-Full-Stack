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

export interface TaskItem {
  id: string;
  title: string;
  description?: string;
  priority: "low" | "medium" | "high";
  estimated_hours: number;
  deadline: string;
}

export interface StudySessionItem {
  id: string;
  plan_id: string;
  topic: string;
  duration_minutes: number;
  scheduled_start: string;
  completed: boolean;
}

export interface StudyPlanItem {
  id: string;
  task_id: string;
  task_title: string;
  generated_at: string;
  status: string;
  sessions: StudySessionItem[];
}

export interface DailyLoadItem {
  date: string;
  total_hours: number;
  event_count: number;
  overloaded: boolean;
}

export interface WorkloadBalanceResponse {
  moved_events_count: number;
  details: string[];
  daily_summary: DailyLoadItem[];
}

export interface SemesterEventItem {
  id: string;
  semester_plan_id: string;
  title: string;
  type: string;
  date: string;
  risk_level: "low" | "medium" | "high";
}

export interface SemesterPlanItem {
  id: string;
  semester_start: string;
  semester_end: string;
  created_at: string;
  events: SemesterEventItem[];
  high_risk_weeks: string[];
}