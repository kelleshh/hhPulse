import type { MetricDefinition, MetricKey, ViewMode } from "./types";

export const METRICS: Record<MetricKey, MetricDefinition> = {
  hhIndex: {
    key: "hhIndex",
    label: "hh-индекс",
    shortLabel: "hh-индекс",
    unit: "ratio",
    description: "Активные резюме за 60 дней на одну вакансию",
  },
  vacancies: {
    key: "vacancies",
    label: "Вакансии",
    shortLabel: "Вакансии",
    unit: "count",
    description: "Активные вакансии в поисковой выдаче HH",
  },
  resumes: {
    key: "resumes",
    label: "Активные резюме",
    shortLabel: "Резюме",
    unit: "count",
    description: "Резюме со статусом поиска работы за последние 60 дней",
  },
  lowResponseShare: {
    key: "lowResponseShare",
    label: "Вакансии с менее чем 10 откликами",
    shortLabel: "<10 откликов",
    unit: "percent",
    description: "Доля вакансий, где HH показывает менее десяти откликов",
  },
  salaryVisibleShare: {
    key: "salaryVisibleShare",
    label: "Вакансии с указанной зарплатой",
    shortLabel: "Зарплата указана",
    unit: "percent",
    description: "Доля вакансий с видимой зарплатной вилкой",
  },
};

export const VIEW_MODES: { value: ViewMode; label: string }[] = [
  { value: "absolute", label: "Значения" },
  { value: "index", label: "Индекс 100" },
  { value: "change", label: "Изменение, %" },
];

export function formatMetric(value: number | null, metric: MetricKey, mode: ViewMode): string {
  if (value === null) return "Нет данных";
  if (mode !== "absolute") return `${value.toLocaleString("ru-RU", { maximumFractionDigits: 1 })}${mode === "change" ? "%" : ""}`;
  const unit = METRICS[metric].unit;
  if (unit === "percent") return `${(value * 100).toLocaleString("ru-RU", { maximumFractionDigits: 1 })}%`;
  return value.toLocaleString("ru-RU", { maximumFractionDigits: unit === "ratio" ? 1 : 0 });
}

export function transformSeries(values: (number | null)[], mode: ViewMode): (number | null)[] {
  if (mode === "absolute") return values;
  const base = values.find((value): value is number => value !== null);
  if (base === undefined || base === 0) return values.map(() => null);
  return values.map((value) => {
    if (value === null) return null;
    const indexed = (value / base) * 100;
    return mode === "index" ? indexed : indexed - 100;
  });
}
