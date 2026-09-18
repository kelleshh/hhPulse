import type { AppSettings, CreateJobInput, Job, MetricKey, RunProgress } from "../domain/types";
import type { ComparisonRequest, DataRepository } from "./contracts";
import {
  DEFAULT_SETTINGS,
  DEMO_ALERTS,
  DEMO_JOBS,
  DEMO_PROGRESS,
  DEMO_ROLES,
  makeSeries,
  makeExperienceSeries,
  makeSnapshot,
  makeRoleMatrix,
  observationDays,
  DEMO_RUN_EVENTS,
} from "./demoData";

const JOBS_KEY = "hhpulse.demo.jobs";
const SETTINGS_KEY = "hhpulse.settings";
const ALERTS_KEY = "hhpulse.demo.alerts";

const pause = () => new Promise((resolve) => window.setTimeout(resolve, 120));

function readJson<T>(key: string, fallback: T): T {
  const value = window.localStorage.getItem(key);
  if (!value) return structuredClone(fallback);
  try {
    return JSON.parse(value) as T;
  } catch {
    return structuredClone(fallback);
  }
}

function writeJson(key: string, value: unknown): void {
  window.localStorage.setItem(key, JSON.stringify(value));
}

export class DemoRepository implements DataRepository {
  async listJobs(): Promise<Job[]> {
    await pause();
    return readJson(JOBS_KEY, DEMO_JOBS);
  }

  async createJob(input: CreateJobInput): Promise<Job> {
    const jobs = await this.listJobs();
    const timestamp = new Date().toISOString();
    const job: Job = {
      id: crypto.randomUUID(),
      ...input,
      methodologyVersion: "hh-index-daily-v1",
      activeResumeWindowDays: 60,
      createdAt: timestamp,
      updatedAt: timestamp,
    };
    writeJson(JOBS_KEY, [...jobs, job]);
    return job;
  }

  async setJobEnabled(jobId: string, enabled: boolean): Promise<Job> {
    const jobs = await this.listJobs();
    const job = jobs.find((item) => item.id === jobId);
    if (!job) throw new Error("Задача не найдена");
    const updated = { ...job, enabled, updatedAt: new Date().toISOString() };
    writeJson(JOBS_KEY, jobs.map((item) => (item.id === jobId ? updated : item)));
    return updated;
  }

  async triggerToday(jobId: string): Promise<boolean> {
    const jobs = await this.listJobs();
    return jobs.some((job) => job.id === jobId && job.enabled);
  }

  async getTodayProgress(jobId: string): Promise<RunProgress | null> {
    await pause();
    return jobId === "moscow-market" ? structuredClone(DEMO_PROGRESS) : null;
  }

  async listRunEvents(jobId: string) {
    await pause();
    return jobId === "moscow-market" ? structuredClone(DEMO_RUN_EVENTS) : [];
  }

  async listRoles() {
    await pause();
    return structuredClone(DEMO_ROLES);
  }

  async getOverview(metric: MetricKey) {
    await pause();
    return {
      observationDays: structuredClone(observationDays),
      primarySeries: makeSeries(["96", "156", "165"], metric, 30),
      metric,
      publishedAt: new Date(Date.now() - 86_400_000).toISOString(),
      rolesObserved: 194,
      observations: 1940,
      activeRun: structuredClone(DEMO_PROGRESS),
      availability30d: 28 / 30,
    };
  }

  async getComparison(request: ComparisonRequest) {
    await pause();
    const series = request.comparisonMode === "experience"
      ? makeExperienceSeries(request.roleIds[0], request.experienceStrata, request.metric, 90)
      : makeSeries(request.roleIds, request.metric, 90);
    return series.map((item) => ({
      ...item,
      points: item.points.filter((point) => point.date >= request.dateFrom && point.date <= request.dateTo),
    }));
  }

  async getSnapshot(date: string, roleId: string) {
    await pause();
    return makeSnapshot(date, roleId);
  }

  async getRoleMatrix() {
    await pause();
    return makeRoleMatrix();
  }

  async listAlerts() {
    await pause();
    return readJson(ALERTS_KEY, DEMO_ALERTS);
  }

  async resolveAlert(alertId: string): Promise<void> {
    const alerts = await this.listAlerts();
    writeJson(
      ALERTS_KEY,
      alerts.map((alert) => (alert.id === alertId ? { ...alert, resolved: true } : alert)),
    );
  }

  async getSettings(): Promise<AppSettings> {
    await pause();
    return readJson(SETTINGS_KEY, DEFAULT_SETTINGS);
  }

  async saveSettings(settings: AppSettings): Promise<AppSettings> {
    writeJson(SETTINGS_KEY, settings);
    return settings;
  }
}
