import type {
  AlertItem,
  AppSettings,
  CreateJobInput,
  Job,
  MarketSeries,
  MetricKey,
  OverviewData,
  Role,
  RunProgress,
  SnapshotData,
} from "../domain/types";

export interface ComparisonRequest {
  comparisonMode: "roles" | "experience";
  roleIds: string[];
  metric: MetricKey;
  experience: string;
  experienceStrata: string[];
  dateFrom: string;
  dateTo: string;
}

export interface DataRepository {
  listJobs(): Promise<Job[]>;
  createJob(input: CreateJobInput): Promise<Job>;
  setJobEnabled(jobId: string, enabled: boolean): Promise<Job>;
  triggerToday(jobId: string): Promise<boolean>;
  getTodayProgress(jobId: string): Promise<RunProgress | null>;
  listRoles(): Promise<Role[]>;
  getOverview(metric: MetricKey): Promise<OverviewData>;
  getComparison(request: ComparisonRequest): Promise<MarketSeries[]>;
  getSnapshot(date: string, roleId: string): Promise<SnapshotData>;
  listAlerts(): Promise<AlertItem[]>;
  resolveAlert(alertId: string): Promise<void>;
  getSettings(): Promise<AppSettings>;
  saveSettings(settings: AppSettings): Promise<AppSettings>;
}

export class DataSourceError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "DataSourceError";
  }
}
