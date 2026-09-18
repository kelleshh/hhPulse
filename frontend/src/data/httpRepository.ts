import { z } from "zod";
import type {
  AlertItem,
  AppSettings,
  CreateJobInput,
  Job,
  MarketSeries,
  MetricKey,
  OverviewData,
  Role,
  RoleMatrixData,
  RunEvent,
  RunProgress,
  SnapshotData,
} from "../domain/types";
import type { ComparisonRequest, DataRepository } from "./contracts";
import { DataSourceError } from "./contracts";
import { DEFAULT_SETTINGS } from "./demoData";

const jobSchema = z.object({
  id: z.string(),
  name: z.string(),
  region_ids: z.array(z.string()),
  role_selection_mode: z.enum(["all", "selected"]),
  role_ids: z.array(z.string()),
  include_experience_strata: z.boolean(),
  max_concurrency: z.number(),
  max_rps: z.number(),
  user_agent_mode: z.enum(["shared", "per_worker"]),
  timezone: z.string(),
  methodology_version: z.string(),
  active_resume_window_days: z.number(),
  enabled: z.boolean(),
  created_at: z.string(),
  updated_at: z.string(),
});

const progressSchema = z.object({
  run_id: z.string(),
  status: z.enum(["planned", "running", "waiting_source", "parser_broken", "failed", "expired", "succeeded"]),
  total_units: z.number(),
  completed_units: z.number(),
  pending_units: z.number(),
  running_units: z.number(),
  waiting_retry_units: z.number(),
  failed_units: z.number(),
  total_attempts: z.number(),
  next_retry_at: z.string().nullable(),
  error_code: z.string().nullable(),
  error_message: z.string().nullable(),
});

const runEventSchema = z.object({
  id: z.number(),
  run_id: z.string(),
  unit_id: z.string().nullable(),
  occurred_at: z.string(),
  level: z.enum(["info", "success", "warning", "error"]),
  event_type: z.string(),
  message: z.string(),
});

function mapJob(value: z.infer<typeof jobSchema>): Job {
  return {
    id: value.id,
    name: value.name,
    regionIds: value.region_ids,
    roleSelectionMode: value.role_selection_mode,
    roleIds: value.role_ids,
    includeExperienceStrata: value.include_experience_strata,
    maxConcurrency: value.max_concurrency,
    maxRps: value.max_rps,
    userAgentMode: value.user_agent_mode,
    timezone: value.timezone,
    methodologyVersion: value.methodology_version,
    activeResumeWindowDays: value.active_resume_window_days,
    enabled: value.enabled,
    createdAt: value.created_at,
    updatedAt: value.updated_at,
  };
}

function mapProgress(value: z.infer<typeof progressSchema>): RunProgress {
  return {
    runId: value.run_id,
    status: value.status,
    totalUnits: value.total_units,
    completedUnits: value.completed_units,
    pendingUnits: value.pending_units,
    runningUnits: value.running_units,
    waitingRetryUnits: value.waiting_retry_units,
    failedUnits: value.failed_units,
    totalAttempts: value.total_attempts,
    nextRetryAt: value.next_retry_at,
    errorCode: value.error_code,
    errorMessage: value.error_message,
  };
}

function toJobPayload(input: CreateJobInput) {
  return {
    name: input.name,
    region_ids: input.regionIds,
    role_selection_mode: input.roleSelectionMode,
    role_ids: input.roleIds,
    include_experience_strata: input.includeExperienceStrata,
    max_concurrency: input.maxConcurrency,
    max_rps: input.maxRps,
    user_agent_mode: input.userAgentMode,
    timezone: input.timezone,
    enabled: input.enabled,
  };
}

export class HttpRepository implements DataRepository {
  constructor(private readonly baseUrl = "") {}

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => null) as { detail?: string } | null;
      throw new DataSourceError(detail?.detail ?? `HTTP ${response.status}`, response.status);
    }
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  }

  async listJobs(): Promise<Job[]> {
    const data = await this.request<unknown>("/api/v1/jobs");
    return z.array(jobSchema).parse(data).map(mapJob);
  }

  async createJob(input: CreateJobInput): Promise<Job> {
    const data = await this.request<unknown>("/api/v1/jobs", {
      method: "POST",
      body: JSON.stringify(toJobPayload(input)),
    });
    return mapJob(jobSchema.parse(data));
  }

  async setJobEnabled(jobId: string, enabled: boolean): Promise<Job> {
    const data = await this.request<unknown>(`/api/v1/jobs/${jobId}/enabled`, {
      method: "PATCH",
      body: JSON.stringify({ enabled }),
    });
    return mapJob(jobSchema.parse(data));
  }

  async triggerToday(jobId: string): Promise<boolean> {
    const data = await this.request<{ accepted: boolean }>(`/api/v1/jobs/${jobId}/runs/today`, { method: "POST" });
    return data.accepted;
  }

  async getTodayProgress(jobId: string): Promise<RunProgress | null> {
    try {
      const data = await this.request<unknown>(`/api/v1/jobs/${jobId}/runs/today`);
      return mapProgress(progressSchema.parse(data));
    } catch (error) {
      if (error instanceof DataSourceError && error.status === 404) return null;
      throw error;
    }
  }

  async listRunEvents(jobId: string): Promise<RunEvent[]> {
    const data = await this.request<unknown>(`/api/v1/jobs/${jobId}/runs/today/events?limit=250`);
    return z.array(runEventSchema).parse(data).map((event) => ({
      id: event.id,
      runId: event.run_id,
      unitId: event.unit_id,
      occurredAt: event.occurred_at,
      level: event.level,
      eventType: event.event_type,
      message: event.message,
    }));
  }

  listRoles(): Promise<Role[]> {
    return this.request<Role[]>("/api/v1/catalog/professional-roles");
  }

  getOverview(metric: MetricKey): Promise<OverviewData> {
    return this.request<OverviewData>(`/api/v1/analytics/overview?metric=${metric}`);
  }

  getComparison(request: ComparisonRequest): Promise<MarketSeries[]> {
    const params = new URLSearchParams({
      role_ids: request.roleIds.join(","),
      comparison_mode: request.comparisonMode,
      metric: request.metric,
      experience: request.experience,
      experience_strata: request.experienceStrata.join(","),
      date_from: request.dateFrom,
      date_to: request.dateTo,
    });
    return this.request<MarketSeries[]>(`/api/v1/analytics/comparison?${params}`);
  }

  getSnapshot(date: string, roleId: string): Promise<SnapshotData> {
    const params = new URLSearchParams({ date, role_id: roleId });
    return this.request<SnapshotData>(`/api/v1/analytics/snapshot?${params}`);
  }

  getRoleMatrix(dateTo?: string): Promise<RoleMatrixData> {
    const params = new URLSearchParams({ history_days: "90" });
    if (dateTo) params.set("date_to", dateTo);
    return this.request<RoleMatrixData>(`/api/v1/analytics/role-matrix?${params}`);
  }

  listAlerts(): Promise<AlertItem[]> {
    return this.request<AlertItem[]>("/api/v1/alerts");
  }

  async resolveAlert(alertId: string): Promise<void> {
    await this.request(`/api/v1/alerts/${alertId}/resolve`, { method: "POST" });
  }

  async getSettings(): Promise<AppSettings> {
    const stored = window.localStorage.getItem("hhpulse.settings");
    return stored ? JSON.parse(stored) as AppSettings : DEFAULT_SETTINGS;
  }

  async saveSettings(settings: AppSettings): Promise<AppSettings> {
    window.localStorage.setItem("hhpulse.settings", JSON.stringify(settings));
    return settings;
  }
}
