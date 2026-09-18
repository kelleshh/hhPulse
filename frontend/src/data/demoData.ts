import { format, subDays } from "date-fns";
import type {
  AlertItem,
  AppSettings,
  Job,
  MarketSeries,
  MetricKey,
  ObservationDay,
  Role,
  RoleMatrixData,
  RunEvent,
  RunProgress,
  SnapshotData,
} from "../domain/types";

export const DEMO_ROLES: Role[] = [
  { id: "96", name: "Программист, разработчик" },
  { id: "156", name: "BI-аналитик, аналитик данных" },
  { id: "10", name: "Аналитик" },
  { id: "165", name: "Дата-сайентист" },
  { id: "164", name: "Продуктовый аналитик" },
  { id: "124", name: "Тестировщик" },
  { id: "160", name: "DevOps-инженер" },
  { id: "104", name: "Руководитель группы разработки" },
  { id: "40", name: "Дизайнер, художник" },
  { id: "70", name: "Менеджер продукта" },
];

const now = new Date();
const isoDay = (daysAgo: number) => format(subDays(now, daysAgo), "yyyy-MM-dd");

export const DEMO_JOBS: Job[] = [
  {
    id: "moscow-market",
    name: "Весь рынок Москвы",
    regionIds: ["1"],
    roleSelectionMode: "all",
    roleIds: [],
    includeExperienceStrata: true,
    maxConcurrency: 2,
    maxRps: 0.8,
    userAgentMode: "shared",
    timezone: "Europe/Moscow",
    methodologyVersion: "hh-index-daily-v1",
    activeResumeWindowDays: 60,
    enabled: true,
    createdAt: `${isoDay(45)}T09:00:00Z`,
    updatedAt: `${isoDay(0)}T08:00:00Z`,
  },
  {
    id: "python-focus",
    name: "Python и данные",
    regionIds: ["1", "2"],
    roleSelectionMode: "selected",
    roleIds: ["96", "156", "165"],
    includeExperienceStrata: true,
    maxConcurrency: 1,
    maxRps: 0.5,
    userAgentMode: "per_worker",
    timezone: "Europe/Moscow",
    methodologyVersion: "hh-index-daily-v1",
    activeResumeWindowDays: 60,
    enabled: true,
    createdAt: `${isoDay(20)}T11:30:00Z`,
    updatedAt: `${isoDay(1)}T11:30:00Z`,
  },
];

export const DEMO_PROGRESS: RunProgress = {
  runId: `run-${isoDay(0)}`,
  status: "running",
  totalUnits: 1940,
  completedUnits: 1264,
  pendingUnits: 672,
  runningUnits: 4,
  waitingRetryUnits: 0,
  failedUnits: 0,
  totalAttempts: 1271,
  nextRetryAt: null,
  errorCode: null,
  errorMessage: null,
  effectiveRps: 0.78,
  response429Count: 1,
  currentRole: "Программист, разработчик",
  currentFilter: "Опыт 1–3 года · резюме",
  startedAt: `${isoDay(0)}T07:12:00Z`,
};

const roleSeed = (roleId: string) => [...roleId].reduce((sum, char) => sum + char.charCodeAt(0), 0);

export function metricValue(metric: MetricKey, day: number, seed: number): number {
  const wave = Math.sin((day + seed) / 6) * 0.035;
  const drift = day * 0.0025;
  if (metric === "hhIndex") return 8.2 + seed * 0.035 + wave * 18 + drift;
  if (metric === "vacancies") return Math.round(1850 + seed * 7 + wave * 900 + day * 5);
  if (metric === "resumes") return Math.round(17500 + seed * 35 + wave * 5200 + day * 28);
  if (metric === "lowResponseShare") return 0.34 + (seed % 8) * 0.018 + wave;
  if (metric === "salaryVisibleShare") return 0.48 + (seed % 7) * 0.02 - wave * 0.4;
  if (metric === "remoteShare") return 0.18 + (seed % 9) * 0.025 + wave;
  if (metric === "hybridShare") return 0.12 + (seed % 6) * 0.018 - wave * 0.2;
  if (metric === "higherEducationShare") return 0.42 + (seed % 8) * 0.03 + wave;
  return 0.08 + (seed % 7) * 0.022 - wave * 0.3;
}

export function makeSeries(roleIds: string[], metric: MetricKey, days = 45): MarketSeries[] {
  const colours = ["#1E5FD2", "#08785B", "#A652B7", "#D27819", "#C84256"];
  return roleIds.map((roleId, index) => {
    const role = DEMO_ROLES.find((item) => item.id === roleId);
    const seed = roleSeed(roleId);
    return {
      id: roleId,
      label: role?.name ?? `Роль ${roleId}`,
      colour: colours[index % colours.length],
      points: Array.from({ length: days }, (_, offset) => {
        const daysAgo = days - offset - 1;
        const missing = daysAgo === 12 || (roleId === "165" && daysAgo === 27);
        return {
          date: isoDay(daysAgo),
          value: missing ? null : metricValue(metric, offset, seed),
        };
      }),
    };
  });
}

const EXPERIENCE_LABELS: Record<string, string> = {
  noExperience: "Без опыта",
  between1And3: "1–3 года",
  between3And6: "3–6 лет",
  moreThan6: "Более 6 лет",
};

export function makeExperienceSeries(roleId: string, strata: string[], metric: MetricKey, days = 45): MarketSeries[] {
  const colours = ["#1E5FD2", "#08785B", "#A652B7", "#D27819"];
  return strata.map((stratum, index) => {
    const seed = roleSeed(`${roleId}-${stratum}`) + index * 13;
    return {
      id: stratum,
      label: EXPERIENCE_LABELS[stratum] ?? stratum,
      colour: colours[index % colours.length],
      points: Array.from({ length: days }, (_, offset) => {
        const daysAgo = days - offset - 1;
        return {
          date: isoDay(daysAgo),
          value: daysAgo === 12 ? null : metricValue(metric, offset, seed),
        };
      }),
    };
  });
}

export const observationDays: ObservationDay[] = Array.from({ length: 30 }, (_, index) => {
  const daysAgo = 29 - index;
  if (daysAgo === 12) return { date: isoDay(daysAgo), state: "gap" };
  if (daysAgo === 5) return { date: isoDay(daysAgo), state: "parser_broken" };
  if (daysAgo === 0) {
    return {
      date: isoDay(daysAgo),
      state: "running",
      completedUnits: DEMO_PROGRESS.completedUnits,
      totalUnits: DEMO_PROGRESS.totalUnits,
    };
  }
  return { date: isoDay(daysAgo), state: "published" };
});

export function makeSnapshot(date: string, roleId: string): SnapshotData {
  const seed = roleSeed(roleId);
  const vacancies = Math.round(metricValue("vacancies", 42, seed));
  const resumes = Math.round(metricValue("resumes", 42, seed));
  const distribution = (items: [string, string, number][]) => {
    const total = items.reduce((sum, [, , value]) => sum + value, 0);
    return items.map(([id, label, value]) => ({ id, label, value, share: value / total }));
  };
  return {
    date,
    roleId,
    roleName: DEMO_ROLES.find((role) => role.id === roleId)?.name ?? "Выбранная роль",
    vacancies,
    resumes,
    hhIndex: resumes / vacancies,
    lowResponseShare: metricValue("lowResponseShare", 42, seed),
    salaryVisibleShare: metricValue("salaryVisibleShare", 42, seed),
    remoteShare: metricValue("remoteShare", 42, seed),
    hybridShare: metricValue("hybridShare", 42, seed),
    higherEducationShare: metricValue("higherEducationShare", 42, seed),
    noExperienceShare: metricValue("noExperienceShare", 42, seed),
    distributions: {
      experience: distribution([
        ["none", "Без опыта", 214],
        ["1-3", "1–3 года", 978],
        ["3-6", "3–6 лет", 532],
        ["6+", "Более 6 лет", 86],
      ]),
      workFormat: distribution([
        ["office", "Офис", 742],
        ["remote", "Удалённо", 611],
        ["hybrid", "Гибрид", 457],
      ]),
      schedule: distribution([
        ["full", "Полный день", 1380],
        ["flex", "Гибкий график", 272],
        ["shift", "Сменный график", 158],
      ]),
      employment: distribution([
        ["full", "Полная занятость", 1601],
        ["part", "Частичная занятость", 122],
        ["project", "Проектная работа", 87],
      ]),
      education: distribution([
        ["higher", "Высшее", 1190],
        ["not_required", "Не требуется", 620],
      ]),
      labels: distribution([
        ["with_salary", "Указан доход", 958],
        ["low_performance", "Меньше 10 откликов", 720],
      ]),
    },
    facets: {},
  };
}

export const DEMO_RUN_EVENTS: RunEvent[] = [
  { id: 3, runId: DEMO_PROGRESS.runId, unitId: "unit-3", occurredAt: new Date().toISOString(), level: "success", eventType: "unit_completed", message: "Получено 2 843: роль 96, any, vacancy, регион 1" },
  { id: 2, runId: DEMO_PROGRESS.runId, unitId: "unit-2", occurredAt: new Date(Date.now() - 2_000).toISOString(), level: "info", eventType: "unit_started", message: "worker-2: запрос: роль 156, any, resume, регион 1" },
  { id: 1, runId: DEMO_PROGRESS.runId, unitId: null, occurredAt: new Date(Date.now() - 60_000).toISOString(), level: "info", eventType: "run_started", message: "План сбора создан: 1940 запросов" },
];

export function makeRoleMatrix(): RoleMatrixData {
  const rows = DEMO_ROLES.map((role) => {
    const seed = roleSeed(role.id);
    const values = Object.fromEntries([
      "hhIndex", "vacancies", "resumes", "lowResponseShare", "salaryVisibleShare",
      "remoteShare", "hybridShare", "higherEducationShare", "noExperienceShare",
    ].map((metric) => [metric, metricValue(metric as MetricKey, 42, seed)])) as Record<MetricKey, number>;
    return {
      roleId: role.id,
      roleName: role.name,
      ...values,
      history: Array.from({ length: 30 }, (_, index) => ({
        date: isoDay(29 - index),
        hhIndex: metricValue("hhIndex", index, seed),
        vacancies: metricValue("vacancies", index, seed),
        resumes: metricValue("resumes", index, seed),
        lowResponseShare: metricValue("lowResponseShare", index, seed),
        salaryVisibleShare: metricValue("salaryVisibleShare", index, seed),
        remoteShare: metricValue("remoteShare", index, seed),
        hybridShare: metricValue("hybridShare", index, seed),
        higherEducationShare: metricValue("higherEducationShare", index, seed),
        noExperienceShare: metricValue("noExperienceShare", index, seed),
      })),
    };
  });
  return { date: isoDay(0), availableDates: [isoDay(0)], rows, statistics: {} };
}

export const DEMO_ALERTS: AlertItem[] = [
  {
    id: "alert-parser",
    severity: "critical",
    title: "Контракт HTML изменился",
    description: "Сбор остановлен до публикации. Документ сохранён в карантине для проверки парсера.",
    occurredAt: `${isoDay(5)}T08:41:00Z`,
    jobName: "Весь рынок Москвы",
    resolved: true,
  },
  {
    id: "alert-rate",
    severity: "warning",
    title: "HH ограничил скорость",
    description: "Получен ответ 429. Скорость снижена до 0,39 запроса в секунду, данные не потеряны.",
    occurredAt: `${isoDay(0)}T09:18:00Z`,
    jobName: "Весь рынок Москвы",
    resolved: false,
  },
];

export const DEFAULT_SETTINGS: AppSettings = {
  defaultMetric: "hhIndex",
  defaultViewMode: "absolute",
  defaultChartGeometry: "line-points",
  compactTables: false,
  reducedDataAnimation: false,
};
