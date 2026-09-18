import { BarChart3, CalendarDays, Grid3X3, Search, Sigma } from "lucide-react";
import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { EmptyState, ErrorState, PageLoading } from "../components/ui/Feedback";
import { useRoleMatrix } from "../data/queries";
import { METRICS, formatMetric } from "../domain/metrics";
import type { MetricKey, MetricStatistics, RoleMatrixRow } from "../domain/types";

const MATRIX_METRICS: MetricKey[] = [
  "hhIndex",
  "vacancies",
  "resumes",
  "lowResponseShare",
  "salaryVisibleShare",
  "remoteShare",
  "hybridShare",
  "higherEducationShare",
  "noExperienceShare",
];

type SortMode = "metric-desc" | "metric-asc" | "name";

function numericValue(row: RoleMatrixRow, metric: MetricKey): number | null {
  const value = row[metric];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function rgbScale(value: number | null, minimum: number, maximum: number): string {
  if (value === null) return "rgb(170, 168, 154)";
  const range = Math.max(maximum - minimum, Number.EPSILON);
  const position = Math.min(1, Math.max(0, (value - minimum) / range));
  const stops = [
    [25, 72, 105],
    [35, 112, 130],
    [71, 145, 125],
    [155, 169, 82],
    [211, 139, 54],
  ];
  const scaled = position * (stops.length - 1);
  const start = Math.min(stops.length - 2, Math.floor(scaled));
  const fraction = scaled - start;
  const channel = (index: number) => Math.round(stops[start][index] + (stops[start + 1][index] - stops[start][index]) * fraction);
  return `rgb(${channel(0)}, ${channel(1)}, ${channel(2)})`;
}

function compact(value: number | null): string {
  if (value === null) return "н/д";
  return Intl.NumberFormat("ru-RU", { notation: value >= 10_000 ? "compact" : "standard", maximumFractionDigits: 1 }).format(value);
}

function correlation(left: Array<number | null>, right: Array<number | null>): number | null {
  const pairs = left.map((value, index) => [value, right[index]] as const).filter((pair): pair is readonly [number, number] => pair[0] !== null && pair[1] !== null);
  if (pairs.length < 3) return null;
  const leftMean = pairs.reduce((sum, pair) => sum + pair[0], 0) / pairs.length;
  const rightMean = pairs.reduce((sum, pair) => sum + pair[1], 0) / pairs.length;
  let numerator = 0;
  let leftSquares = 0;
  let rightSquares = 0;
  for (const pair of pairs) {
    const leftDelta = pair[0] - leftMean;
    const rightDelta = pair[1] - rightMean;
    numerator += leftDelta * rightDelta;
    leftSquares += leftDelta ** 2;
    rightSquares += rightDelta ** 2;
  }
  const denominator = Math.sqrt(leftSquares * rightSquares);
  return denominator === 0 ? null : numerator / denominator;
}

export function ProfessionConsolePage() {
  const [dateTo, setDateTo] = useState("");
  const [metric, setMetric] = useState<MetricKey>("hhIndex");
  const [search, setSearch] = useState("");
  const [sortMode, setSortMode] = useState<SortMode>("metric-desc");
  const matrix = useRoleMatrix(dateTo || undefined);

  const rows = useMemo(() => {
    const query = search.trim().toLocaleLowerCase("ru-RU");
    const result = (matrix.data?.rows ?? []).filter((row) => !query || row.roleName.toLocaleLowerCase("ru-RU").includes(query));
    return [...result].sort((left, right) => {
      if (sortMode === "name") return left.roleName.localeCompare(right.roleName, "ru");
      const direction = sortMode === "metric-desc" ? -1 : 1;
      return direction * ((numericValue(left, metric) ?? Number.NEGATIVE_INFINITY) - (numericValue(right, metric) ?? Number.NEGATIVE_INFINITY));
    });
  }, [matrix.data?.rows, metric, search, sortMode]);

  if (matrix.isLoading) return <PageLoading label="Собираю матрицу всех профессий" />;
  if (matrix.error) return <ErrorState error={matrix.error} onRetry={() => matrix.refetch()} />;
  if (!matrix.data?.rows.length) {
    return (
      <div className="page">
        <header className="page-heading"><h1>Пульт профессий</h1><p>Единая поверхность для анализа всех профессиональных ролей.</p></header>
        <EmptyState title="Матрица пока пуста" description="Создайте задачу сбора, запустите её и дождитесь публикации полного дневного среза. После этого здесь появятся все профессии и распределения." />
      </div>
    );
  }

  const values = rows.map((row) => numericValue(row, metric)).filter((value): value is number => value !== null);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const statistics = matrix.data.statistics[metric];

  return (
    <div className="page console-page">
      <header className="page-heading page-heading--split console-heading">
        <div>
          <span className="console-kicker">ANALYTICAL CONTROL SURFACE / {matrix.data.date}</span>
          <h1>Пульт профессий</h1>
          <p>{matrix.data.rows.length} ролей · 9 показателей · до 90 дней истории. Один цвет всегда означает одно место на шкале.</p>
        </div>
        <div className="console-heading__stamp"><Grid3X3 size={18} /><span>Срез опубликован<strong>{matrix.data.date}</strong></span></div>
      </header>

      <section className="console-toolbar" aria-label="Настройки пульта">
        <label className="field"><span>Показатель</span><select value={metric} onChange={(event) => setMetric(event.target.value as MetricKey)}>{MATRIX_METRICS.map((key) => <option key={key} value={key}>{METRICS[key].label}</option>)}</select></label>
        <label className="field"><span>Срез не позднее</span><div className="input-with-icon"><CalendarDays size={16} /><input type="date" value={dateTo} max={new Date().toISOString().slice(0, 10)} onChange={(event) => setDateTo(event.target.value)} /></div></label>
        <label className="field console-search"><span>Фильтр профессий</span><div className="input-with-icon"><Search size={16} /><input type="search" value={search} placeholder="Название роли" onChange={(event) => setSearch(event.target.value)} /></div></label>
        <label className="field"><span>Порядок карточек</span><select value={sortMode} onChange={(event) => setSortMode(event.target.value as SortMode)}><option value="metric-desc">По убыванию</option><option value="metric-asc">По возрастанию</option><option value="name">По алфавиту</option></select></label>
      </section>

      <StatisticsStrip statistics={statistics} metric={metric} />

      <div className="console-chart-grid">
        <DistributionPanel rows={rows} metric={metric} minimum={minimum} maximum={maximum} />
        <RankPanel rows={rows} metric={metric} minimum={minimum} maximum={maximum} />
        <MarketScatterPanel rows={rows} metric={metric} minimum={minimum} maximum={maximum} />
        <CorrelationPanel rows={rows} />
      </div>

      <section className="role-bank">
        <div className="section-heading section-heading--split">
          <div><h2>Банк индикаторов</h2><p>Все профессии в одном поле. Мини-график показывает динамику выбранного показателя.</p></div>
          <span className="role-bank__counter">ПОКАЗАНО {rows.length} / {matrix.data.rows.length}</span>
        </div>
        {rows.length ? (
          <div className="role-card-grid">
            {rows.map((row, index) => <RoleCard key={row.roleId} row={row} metric={metric} minimum={minimum} maximum={maximum} rank={index + 1} />)}
          </div>
        ) : <EmptyState title="Ничего не найдено" description="Измените строку фильтра профессий." />}
      </section>
    </div>
  );
}

function StatisticsStrip({ statistics, metric }: { statistics?: MetricStatistics; metric: MetricKey }) {
  const cells: Array<[string, number | null | undefined]> = [
    ["MIN", statistics?.min], ["Q1", statistics?.q1], ["MED", statistics?.median], ["MEAN", statistics?.mean],
    ["Q3", statistics?.q3], ["MAX", statistics?.max], ["SD", statistics?.stddev], ["N", statistics?.count],
  ];
  return <section className="statistics-strip" aria-label="Описательная статистика">{cells.map(([label, value]) => <div key={label}><span>{label}</span><strong>{label === "N" ? compact(value ?? null) : formatMetric(value ?? null, metric, "absolute")}</strong></div>)}</section>;
}

function DistributionPanel({ rows, metric, minimum, maximum }: { rows: RoleMatrixRow[]; metric: MetricKey; minimum: number; maximum: number }) {
  const values = rows.map((row) => numericValue(row, metric)).filter((value): value is number => value !== null).sort((a, b) => a - b);
  const binCount = Math.min(14, Math.max(5, Math.ceil(Math.sqrt(values.length))));
  const width = Math.max((maximum - minimum) / binCount, Number.EPSILON);
  const bins = Array.from({ length: binCount }, (_, index) => ({
    from: minimum + index * width,
    to: index === binCount - 1 ? maximum : minimum + (index + 1) * width,
    count: 0,
  }));
  for (const value of values) bins[Math.min(binCount - 1, Math.floor((value - minimum) / width))].count += 1;
  return (
    <section className="console-panel">
      <PanelHeading icon={<BarChart3 size={17} />} code="DISTR-01" title="Распределение" description="Частоты по правилу квадратного корня" />
      <div className="console-chart">
        <ResponsiveContainer width="100%" height="100%"><BarChart data={bins} margin={{ top: 12, right: 8, left: -18, bottom: 3 }}><CartesianGrid stroke="rgb(201, 197, 177)" vertical={false} /><XAxis dataKey="from" tickFormatter={(value) => compact(Number(value))} tick={{ fontSize: 10, fill: "rgb(72,71,62)" }} /><YAxis allowDecimals={false} tick={{ fontSize: 10, fill: "rgb(72,71,62)" }} /><Tooltip labelFormatter={(value) => `от ${formatMetric(Number(value), metric, "absolute")}`} formatter={(value) => [`${value} профессий`, "Частота"]} /><Bar dataKey="count" isAnimationActive={false}>{bins.map((bin) => <Cell key={bin.from} fill={rgbScale((bin.from + bin.to) / 2, minimum, maximum)} />)}</Bar></BarChart></ResponsiveContainer>
      </div>
    </section>
  );
}

function RankPanel({ rows, metric, minimum, maximum }: { rows: RoleMatrixRow[]; metric: MetricKey; minimum: number; maximum: number }) {
  const ranked = [...rows].filter((row) => numericValue(row, metric) !== null).sort((left, right) => (numericValue(left, metric) ?? 0) - (numericValue(right, metric) ?? 0)).map((row, index) => ({ rank: index + 1, value: numericValue(row, metric), name: row.roleName }));
  return (
    <section className="console-panel">
      <PanelHeading icon={<Sigma size={17} />} code="RANK-02" title="Ранговая функция" description="Все роли в порядке выбранной метрики" />
      <div className="console-chart"><ResponsiveContainer width="100%" height="100%"><ScatterChart margin={{ top: 12, right: 12, left: -15, bottom: 3 }}><CartesianGrid stroke="rgb(201, 197, 177)" /><XAxis type="number" dataKey="rank" name="Ранг" tick={{ fontSize: 10 }} /><YAxis type="number" dataKey="value" tickFormatter={compact} tick={{ fontSize: 10 }} /><Tooltip cursor={{ strokeDasharray: "3 3" }} formatter={(value, name) => [name === "value" ? formatMetric(Number(value), metric, "absolute") : value, name === "value" ? METRICS[metric].shortLabel : name]} labelFormatter={(_, payload) => payload[0]?.payload.name ?? ""} /><Scatter data={ranked} isAnimationActive={false}>{ranked.map((item) => <Cell key={item.rank} fill={rgbScale(item.value, minimum, maximum)} />)}</Scatter></ScatterChart></ResponsiveContainer></div>
    </section>
  );
}

function MarketScatterPanel({ rows, metric, minimum, maximum }: { rows: RoleMatrixRow[]; metric: MetricKey; minimum: number; maximum: number }) {
  const points = rows.filter((row) => row.vacancies > 0 && row.resumes > 0).map((row) => ({ x: row.vacancies, y: row.resumes, z: Math.max(30, numericValue(row, metric) ?? 30), metric: numericValue(row, metric), name: row.roleName, hhIndex: row.hhIndex }));
  return (
    <section className="console-panel console-panel--wide">
      <PanelHeading icon={<Grid3X3 size={17} />} code="PHASE-03" title="Фазовая плоскость рынка" description="Логарифмы вакансий и резюме; размер и цвет — выбранный показатель" />
      <div className="console-chart console-chart--large"><ResponsiveContainer width="100%" height="100%"><ScatterChart margin={{ top: 12, right: 18, left: 0, bottom: 8 }}><CartesianGrid stroke="rgb(201, 197, 177)" /><XAxis type="number" dataKey="x" name="Вакансии" scale="log" domain={[1, "auto"]} tickFormatter={compact} tick={{ fontSize: 10 }} /><YAxis type="number" dataKey="y" name="Резюме" scale="log" domain={[1, "auto"]} tickFormatter={compact} tick={{ fontSize: 10 }} /><ZAxis type="number" dataKey="z" range={[35, 260]} /><ReferenceLine stroke="rgb(92, 89, 76)" strokeDasharray="4 3" /><Tooltip cursor={{ strokeDasharray: "3 3" }} content={<ScatterTooltip metric={metric} />} /><Scatter data={points} isAnimationActive={false}>{points.map((point) => <Cell key={point.name} fill={rgbScale(point.metric, minimum, maximum)} fillOpacity={0.82} stroke="rgb(35,35,29)" strokeWidth={0.5} />)}</Scatter></ScatterChart></ResponsiveContainer></div>
    </section>
  );
}

function ScatterTooltip({ active, payload, metric }: { active?: boolean; payload?: Array<{ payload: { name: string; x: number; y: number; metric: number | null; hhIndex: number | null } }>; metric: MetricKey }) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return <div className="console-tooltip"><strong>{point.name}</strong><span>Вакансии: {compact(point.x)}</span><span>Резюме: {compact(point.y)}</span><span>{METRICS[metric].shortLabel}: {formatMetric(point.metric, metric, "absolute")}</span></div>;
}

function CorrelationPanel({ rows }: { rows: RoleMatrixRow[] }) {
  const selected: MetricKey[] = ["hhIndex", "vacancies", "resumes", "salaryVisibleShare", "remoteShare", "noExperienceShare"];
  return (
    <section className="console-panel console-panel--correlation">
      <PanelHeading icon={<Sigma size={17} />} code="CORR-04" title="Матрица корреляций" description="Коэффициент Пирсона по доступным парам" />
      <div className="correlation-table"><table><thead><tr><th /><>{selected.map((metric) => <th key={metric} title={METRICS[metric].label}>{METRICS[metric].shortLabel}</th>)}</></tr></thead><tbody>{selected.map((left) => <tr key={left}><th>{METRICS[left].shortLabel}</th>{selected.map((right) => { const value = correlation(rows.map((row) => numericValue(row, left)), rows.map((row) => numericValue(row, right))); return <td key={right} style={{ background: value === null ? "rgb(205,202,187)" : rgbScale(value, -1, 1), color: value !== null && Math.abs(value) > 0.55 ? "white" : "rgb(30,30,25)" }} title={`${METRICS[left].label} × ${METRICS[right].label}`}><strong>{value?.toFixed(2) ?? "—"}</strong></td>; })}</tr>)}</tbody></table></div>
    </section>
  );
}

function PanelHeading({ icon, code, title, description }: { icon: React.ReactNode; code: string; title: string; description: string }) {
  return <div className="console-panel__heading"><span className="console-panel__icon">{icon}</span><div><small>{code}</small><h2>{title}</h2><p>{description}</p></div></div>;
}

function RoleCard({ row, metric, minimum, maximum, rank }: { row: RoleMatrixRow; metric: MetricKey; minimum: number; maximum: number; rank: number }) {
  const value = numericValue(row, metric);
  const history = row.history.map((point) => point[metric]).filter((item): item is number => typeof item === "number" && Number.isFinite(item));
  const historyMinimum = history.length ? Math.min(...history) : 0;
  const historyMaximum = history.length ? Math.max(...history) : 1;
  const points = history.map((item, index) => {
    const x = history.length === 1 ? 50 : (index / (history.length - 1)) * 100;
    const y = 30 - ((item - historyMinimum) / Math.max(historyMaximum - historyMinimum, Number.EPSILON)) * 27;
    return `${x},${y}`;
  }).join(" ");
  return (
    <article className="role-card" style={{ borderTopColor: rgbScale(value, minimum, maximum) }}>
      <div className="role-card__head"><span>#{String(rank).padStart(3, "0")}</span><small>ID {row.roleId}</small></div>
      <h3 title={row.roleName}>{row.roleName}</h3>
      <div className="role-card__reading"><strong>{formatMetric(value, metric, "absolute")}</strong><small>{METRICS[metric].shortLabel}</small></div>
      <svg className="sparkline" viewBox="0 0 100 32" preserveAspectRatio="none" aria-label={`Динамика: ${row.roleName}`}><line x1="0" x2="100" y1="30" y2="30" /><polyline points={points} style={{ stroke: rgbScale(value, minimum, maximum) }} /></svg>
      <div className="role-card__foot"><span>VAC <b>{compact(row.vacancies)}</b></span><span>CV <b>{compact(row.resumes)}</b></span><span>HH <b>{row.hhIndex?.toFixed(1) ?? "—"}</b></span></div>
    </article>
  );
}
