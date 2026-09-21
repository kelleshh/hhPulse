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
  deleteJob(jobId: string): Promise<void>;
  setJobEnabled(jobId: string, enabled: boolean): Promise<Job>;
  triggerToday(jobId: string): Promise<boolean>;
  getTodayProgress(jobId: string): Promise<RunProgress | null>;
  listRunEvents(jobId: string): Promise<RunEvent[]>;
  listRoles(): Promise<Role[]>;
  getOverview(metric: MetricKey): Promise<OverviewData>;
  getComparison(request: ComparisonRequest): Promise<MarketSeries[]>;
  getSnapshot(date: string, roleId: string): Promise<SnapshotData>;
  getRoleMatrix(dateTo?: string): Promise<RoleMatrixData>;
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
