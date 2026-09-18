import { Activity, ArrowUpRight, Clock3, Layers3 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ComparisonChart } from "../components/charts/ComparisonChart";
import { MarketTape } from "../components/charts/MarketTape";
import { ErrorState, PageLoading } from "../components/ui/Feedback";
import { SegmentedControl } from "../components/ui/SegmentedControl";
import { StatusBadge } from "../components/ui/StatusBadge";
import { useOverview, useSettings } from "../data/queries";
import { CHART_GEOMETRIES, METRICS, VIEW_MODES } from "../domain/metrics";
import type { ChartGeometry, MetricKey, ViewMode } from "../domain/types";

export function DashboardPage() {
  const navigate = useNavigate();
  const [metric, setMetric] = useState<MetricKey>("hhIndex");
  const [mode, setMode] = useState<ViewMode>("absolute");
  const [geometry, setGeometry] = useState<ChartGeometry>("line-points");
  const settings = useSettings();
  const defaultsApplied = useRef(false);
  const overview = useOverview(metric);

  useEffect(() => {
    if (!settings.data || defaultsApplied.current) return;
    setMetric(settings.data.defaultMetric);
    setMode(settings.data.defaultViewMode);
    setGeometry(settings.data.defaultChartGeometry);
    defaultsApplied.current = true;
  }, [settings.data]);

  if (overview.isLoading) return <PageLoading label="Загружаю обзор рынка" />;
  if (overview.error || !overview.data) return <ErrorState error={overview.error} onRetry={() => overview.refetch()} />;

  const data = overview.data;
  const run = data.activeRun;
  const progress = run && run.totalUnits > 0 ? (run.completedUnits / run.totalUnits) * 100 : 0;

  return (
    <div className="page page--dashboard">
      <header className="page-heading page-heading--split">
        <div>
          <h1>Рынок труда сегодня</h1>
          <p>Состояние сбора и динамика ключевых профессий без скачивания отдельных вакансий.</p>
        </div>
        <Link className="text-link" to="/compare">Открыть сравнение <ArrowUpRight size={17} /></Link>
      </header>

      <MarketTape days={data.observationDays} onSelect={(day) => navigate(`/snapshot?date=${day.date}`)} />

      <section className="measure-strip" aria-label="Сводка наблюдений">
        <div><Layers3 size={19} /><span><strong>{data.rolesObserved}</strong><small>профессии в плане</small></span></div>
        <div><Activity size={19} /><span><strong>{data.observations.toLocaleString("ru-RU")}</strong><small>наблюдений в полном дне</small></span></div>
        <div><Clock3 size={19} /><span><strong>{(data.availability30d * 100).toFixed(0)}%</strong><small>дней опубликовано за месяц</small></span></div>
        <div className="measure-strip__method"><span><strong>60 дней</strong><small>окно активности резюме</small></span></div>
      </section>

      {run ? (
        <section className="run-ribbon" aria-labelledby="today-run-title">
          <div className="run-ribbon__status">
            <StatusBadge status={run.status} />
            <div>
              <h2 id="today-run-title">Сегодняшний срез</h2>
              <p>{run.currentRole} · {run.currentFilter}</p>
            </div>
          </div>
          <div className="run-ribbon__progress">
            <div className="progress-label">
              <strong>{run.completedUnits.toLocaleString("ru-RU")} / {run.totalUnits.toLocaleString("ru-RU")}</strong>
              <span>{progress.toFixed(0)}%</span>
            </div>
            <div className="progress-track"><span style={{ width: `${progress}%` }} /></div>
          </div>
          <dl className="run-ribbon__metrics">
            <div><dt>Текущая скорость</dt><dd>{run.effectiveRps?.toLocaleString("ru-RU")} запр./с</dd></div>
            <div><dt>Повторные попытки</dt><dd>{Math.max(0, run.totalAttempts - run.completedUnits)}</dd></div>
            <div><dt>Ответы 429</dt><dd>{run.response429Count ?? 0}</dd></div>
          </dl>
          <Link className="button button--secondary button--small" to={`/jobs/${run.jobId ?? ""}`}>Подробнее</Link>
        </section>
      ) : null}

      <section className="analysis-panel">
        <div className="analysis-panel__heading">
          <div>
            <h2>Динамика конкуренции</h2>
            <p>Три выбранные профессии, последние 30 опубликованных дней.</p>
          </div>
          <div className="analysis-panel__controls">
            <label className="field field--inline">
              <span>Показатель</span>
              <select value={metric} onChange={(event) => setMetric(event.target.value as MetricKey)}>
                {Object.values(METRICS).map((item) => <option key={item.key} value={item.key}>{item.shortLabel}</option>)}
              </select>
            </label>
            <SegmentedControl label="Режим значений" value={mode} options={VIEW_MODES} onChange={setMode} />
            <label className="field field--inline"><span>Геометрия</span><select value={geometry} onChange={(event) => setGeometry(event.target.value as ChartGeometry)}>{CHART_GEOMETRIES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
          </div>
        </div>
        {data.primarySeries.length ? <ComparisonChart series={data.primarySeries} metric={metric} mode={mode} geometry={geometry} /> : <div className="data-vacuum"><strong>Пока нет опубликованных наблюдений</strong><span>Создайте задачу сбора и дождитесь полной публикации первого дня.</span></div>}
      </section>
    </div>
  );
}
