import { Save } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Button } from "../components/ui/Button";
import { ErrorState, PageLoading } from "../components/ui/Feedback";
import { SegmentedControl } from "../components/ui/SegmentedControl";
import { Toggle } from "../components/ui/Toggle";
import { useSaveSettings, useSettings } from "../data/queries";
import { dataMode } from "../data/repository";
import { CHART_GEOMETRIES, METRICS, VIEW_MODES } from "../domain/metrics";
import type { AppSettings, ChartGeometry, MetricKey } from "../domain/types";

export function SettingsPage() {
  const settings = useSettings();
  const save = useSaveSettings();
  const [form, setForm] = useState<AppSettings | null>(null);

  useEffect(() => {
    if (settings.data) setForm(settings.data);
  }, [settings.data]);

  if (settings.isLoading || !form) return <PageLoading label="Загружаю настройки" />;
  if (settings.error) return <ErrorState error={settings.error} onRetry={() => settings.refetch()} />;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate(form);
  };

  return (
    <div className="page page--narrow">
      <header className="page-heading"><h1>Настройки интерфейса</h1><p>Личные значения по умолчанию. Параметры сбора меняются в каждой задаче отдельно.</p></header>
      <form className="settings-form" onSubmit={submit}>
        <section>
          <div className="section-heading"><h2>Аналитика по умолчанию</h2><p>Используется при первом открытии обзора и сравнения.</p></div>
          <label className="field"><span>Показатель</span><select value={form.defaultMetric} onChange={(event) => setForm({ ...form, defaultMetric: event.target.value as MetricKey })}>{Object.values(METRICS).map((metric) => <option key={metric.key} value={metric.key}>{metric.label}</option>)}</select></label>
          <div className="field"><span>Режим шкалы</span><SegmentedControl label="Режим шкалы" value={form.defaultViewMode} options={VIEW_MODES} onChange={(defaultViewMode) => setForm({ ...form, defaultViewMode })} /></div>
          <label className="field"><span>Геометрия графика</span><select value={form.defaultChartGeometry} onChange={(event) => setForm({ ...form, defaultChartGeometry: event.target.value as ChartGeometry })}>{CHART_GEOMETRIES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
        </section>
        <section>
          <div className="section-heading"><h2>Отображение</h2><p>Настройки хранятся только в этом браузере.</p></div>
          <Toggle checked={form.compactTables} onChange={(compactTables) => setForm({ ...form, compactTables })} label="Компактные таблицы" description="Уменьшает высоту строк в больших выгрузках" />
          <Toggle checked={form.reducedDataAnimation} onChange={(reducedDataAnimation) => setForm({ ...form, reducedDataAnimation })} label="Не анимировать обновление данных" description="Полезно при частом обновлении прогресса" />
        </section>
        <section>
          <div className="section-heading"><h2>Подключение</h2><p>Текущий режим задаётся при сборке фронтенда.</p></div>
          <dl className="connection-info"><div><dt>Источник данных</dt><dd>{dataMode === "demo" ? "Демонстрационный набор" : "Локальный FastAPI"}</dd></div><div><dt>Адрес API</dt><dd>{dataMode === "demo" ? "API не используется" : (import.meta.env.VITE_API_BASE_URL || "тот же адрес")}</dd></div></dl>
        </section>
        <div className="settings-form__actions"><Button type="submit" variant="primary" icon={<Save size={17} />} disabled={save.isPending}>{save.isPending ? "Сохраняю…" : "Сохранить настройки"}</Button>{save.isSuccess ? <span role="status">Сохранено</span> : null}</div>
      </form>
    </div>
  );
}
