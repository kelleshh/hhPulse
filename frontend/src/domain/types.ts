export type RunStatus =
  | "planned"
  | "running"
  | "waiting_source"
  | "parser_broken"
  | "failed"
  | "expired"
  | "succeeded";

export type UnitStatus = "pending" | "running" | "waiting_retry" | "failed" | "succeeded";
export type UserAgentMode = "shared" | "per_worker";
export type RoleSelectionMode = "all" | "selected";
export type ViewMode = "absolute" | "index" | "change";
export type MetricKey =
  | "hhIndex"
  | "vacancies"
  | "resumes"
  | "lowResponseShare"
  | "salaryVisibleShare";

export interface Job {
  id: string;
  name: string;
  regionIds: string[];
  roleSelectionMode: RoleSelectionMode;
  roleIds: string[];
  includeExperienceStrata: boolean;
  maxConcurrency: number;
  maxRps: number;
  userAgentMode: UserAgentMode;
  timezone: string;
  methodologyVersion: string;
  activeResumeWindowDays: number;
  enabled: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface CreateJobInput {
  name: string;
  regionIds: string[];
  roleSelectionMode: RoleSelectionMode;
  roleIds: string[];
  includeExperienceStrata: boolean;
  maxConcurrency: number;
  maxRps: number;
  userAgentMode: UserAgentMode;
  timezone: string;
  enabled: boolean;
}

export interface RunProgress {
  runId: string;
  status: RunStatus;
  totalUnits: number;
  completedUnits: number;
  pendingUnits: number;
  runningUnits: number;
  waitingRetryUnits: number;
  failedUnits: number;
  totalAttempts: number;
  nextRetryAt: string | null;
  errorCode: string | null;
  errorMessage: string | null;
  effectiveRps?: number;
  response429Count?: number;
  currentRole?: string;
  currentFilter?: string;
  startedAt?: string;
}

export interface Role {
  id: string;
  name: string;
}

export interface MetricDefinition {
  key: MetricKey;
  label: string;
  shortLabel: string;
  unit: "count" | "ratio" | "percent";
  description: string;
}

export interface SeriesPoint {
  date: string;
  value: number | null;
}

export interface MarketSeries {
  id: string;
  label: string;
  colour: string;
  points: SeriesPoint[];
}

export type ObservationState = "published" | "gap" | "running" | "parser_broken";

export interface ObservationDay {
  date: string;
  state: ObservationState;
  completedUnits?: number;
  totalUnits?: number;
}

export interface OverviewData {
  observationDays: ObservationDay[];
  primarySeries: MarketSeries[];
  metric: MetricKey;
  publishedAt: string | null;
  rolesObserved: number;
  observations: number;
  activeRun: RunProgress | null;
  availability30d: number;
}

export interface DistributionItem {
  id: string;
  label: string;
  value: number;
  share: number;
}

export interface SnapshotData {
  date: string;
  roleId: string;
  roleName: string;
  vacancies: number;
  resumes: number;
  hhIndex: number;
  lowResponseShare: number;
  salaryVisibleShare: number;
  distributions: {
    experience: DistributionItem[];
    workFormat: DistributionItem[];
    schedule: DistributionItem[];
    employment: DistributionItem[];
  };
}

export type AlertSeverity = "critical" | "warning" | "info";

export interface AlertItem {
  id: string;
  severity: AlertSeverity;
  title: string;
  description: string;
  occurredAt: string;
  jobName: string;
  resolved: boolean;
}

export interface AppSettings {
  defaultMetric: MetricKey;
  defaultViewMode: ViewMode;
  compactTables: boolean;
  reducedDataAnimation: boolean;
}
