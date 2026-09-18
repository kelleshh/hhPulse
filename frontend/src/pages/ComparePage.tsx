import { Download, Search, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { ComparisonChart } from "../components/charts/ComparisonChart";
import { Button } from "../components/ui/Button";
import { EmptyState, ErrorState, PageLoading } from "../components/ui/Feedback";
import { SegmentedControl } from "../components/ui/SegmentedControl";
import { useComparison, useRoles, useSettings } from "../data/queries";
import { METRICS, VIEW_MODES } from "../domain/metrics";
import type { MarketSeries, MetricKey, ViewMode } from "../domain/types";

const today = new Date();
const dateTo = today.toISOString().slice(0, 10);
const dateFrom = new Date(today.getTime() - 44 * 86_400_000).toISOString().slice(0, 10);

function exportSeries(series: MarketSeries[], metric: MetricKey): void {
  const dates = [...new Set(series.flatMap((item) => item.points.map((point) => point.date)))].sort();
  const header = ["date", ...series.map((item) => item.label)];
  const rows = dates.map((date) => [
    date,
    ...series.map((item) => item.points.find((point) => point.date === date)?.value ?? ""),
  ]);
  const csv = [header, ...rows].map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(",")).join("\n");
  const url = URL.createObjectURL(new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `hhpulse-${metric}-${dateFrom}-${dateTo}.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function ComparePage() {
  const roles = useRoles();
  const [comparisonMode, setComparisonMode] = useState<"roles" | "experience">("roles");
  const [selected, setSelected] = useState(["96", "156", "165"]);
  const [metric, setMetric] = useState<MetricKey>("hhIndex");
  const [mode, setMode] = useState<ViewMode>("absolute");
  const [experience, setExperience] = useState("any");
  const [experienceStrata, setExperienceStrata] = useState(["noExperience", "between1And3", "between3And6", "moreThan6"]);
  const [query, setQuery] = useState("");
  const [from, setFrom] = useState(dateFrom);
  const [to, setTo] = useState(dateTo);
  const settings = useSettings();
  const defaultsApplied = useRef(false);
  const request = useMemo(() => ({ comparisonMode, roleIds: selected, metric, experience, experienceStrata, dateFrom: from, dateTo: to }), [comparisonMode, selected, metric, experience, experienceStrata, from, to]);
  const comparison = useComparison(request);

  useEffect(() => {
    if (!settings.data || defaultsApplied.current) return;
    setMetric(settings.data.defaultMetric);
    setMode(settings.data.defaultViewMode);
    defaultsApplied.current = true;
  }, [settings.data]);

  const filteredRoles = roles.data?.filter((role) => role.name.toLocaleLowerCase("ru").includes(query.toLocaleLowerCase("ru"))) ?? [];
  const toggleRole = (roleId: string) => {
    if (comparisonMode === "experience") {
      setSelected([roleId]);
      return;
    }
    setSelected((current) => current.includes(roleId)
      ? current.filter((id) => id !== roleId)
      : current.length < 5 ? [...current, roleId] : current);
  };

  const changeMode = (value: "roles" | "experience") => {
    setComparisonMode(value);
    if (value === "experience") setSelected((current) => current.slice(0, 1));
  };

  const toggleStratum = (stratum: string) => {
    setExperienceStrata((current) => current.includes(stratum)
      ? current.length > 1 ? current.filter((item) => item !== stratum) : current
      : [...current, stratum]);
  };

  return (
    <div className="page">
      <header className="page-heading">
        <h1>Сравнение профессий</h1>
        <p>Сравнивайте до пяти профессий или страты опыта внутри одной профессии на общей шкале.</p>
      </header>

      <SegmentedControl
        label="Что сравнивать"
        value={comparisonMode}
        options={[{ value: "roles", label: "Профессии" }, { value: "experience", label: "Страты опыта" }]}
        onChange={changeMode}
      />

      <div className="comparison-workspace">
        <aside className="filter-panel" aria-label="Параметры сравнения">
          <div className="filter-section">
            <label className="field">
              <span>Найти профессию</span>
              <div className="input-with-icon"><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Например, аналитик" /></div>
            </label>
            <div className="selected-roles" aria-label="Выбранные профессии">
              {selected.map((roleId) => {
                const role = roles.data?.find((item) => item.id === roleId);
                return <button key={roleId} disabled={comparisonMode === "experience"} onClick={() => toggleRole(roleId)}>{role?.name ?? roleId}{comparisonMode === "roles" ? <X size={14} /> : null}</button>;
              })}
            </div>
            <div className="role-options">
              {roles.isLoading ? <PageLoading label="Загружаю профессии" /> : filteredRoles.map((role) => (
                <label key={role.id} className={selected.includes(role.id) ? "is-selected" : ""}>
                  <input type={comparisonMode === "roles" ? "checkbox" : "radio"} name={comparisonMode === "experience" ? "comparison-role" : undefined} checked={selected.includes(role.id)} disabled={comparisonMode === "roles" && !selected.includes(role.id) && selected.length >= 5} onChange={() => toggleRole(role.id)} />
                  <span>{role.name}</span>
                </label>
              ))}
            </div>
            <small className="field-hint">{comparisonMode === "roles" ? `Выбрано ${selected.length} из 5` : "Выберите одну профессию"}</small>
          </div>
          <div className="filter-section">
            {comparisonMode === "roles" ? (
              <label className="field">
                <span>Опыт</span>
                <select value={experience} onChange={(event) => setExperience(event.target.value)}>
                  <option value="any">Любой опыт</option>
                  <option value="noExperience">Без опыта</option>
                  <option value="between1And3">1–3 года</option>
                  <option value="between3And6">3–6 лет</option>
                  <option value="moreThan6">Более 6 лет</option>
                </select>
              </label>
            ) : (
              <fieldset className="strata-options">
                <legend>Страты на графике</legend>
                {[
                  ["noExperience", "Без опыта"],
                  ["between1And3", "1–3 года"],
                  ["between3And6", "3–6 лет"],
                  ["moreThan6", "Более 6 лет"],
                ].map(([value, label]) => <label key={value}><input type="checkbox" checked={experienceStrata.includes(value)} onChange={() => toggleStratum(value)} />{label}</label>)}
              </fieldset>
            )}
            <label className="field"><span>От</span><input type="date" value={from} max={to} onChange={(event) => setFrom(event.target.value)} /></label>
            <label className="field"><span>До</span><input type="date" value={to} min={from} max={dateTo} onChange={(event) => setTo(event.target.value)} /></label>
          </div>
        </aside>

        <section className="analysis-panel analysis-panel--workspace">
          <div className="analysis-panel__heading">
            <div>
              <h2>{METRICS[metric].label}{comparisonMode === "experience" ? " по опыту" : ""}</h2>
              <p>{METRICS[metric].description}</p>
            </div>
            <Button variant="quiet" size="small" icon={<Download size={16} />} disabled={!comparison.data?.length} onClick={() => comparison.data && exportSeries(comparison.data, metric)}>CSV</Button>
          </div>
          <div className="chart-toolbar">
            <label className="field field--inline">
              <span>Показатель</span>
              <select value={metric} onChange={(event) => setMetric(event.target.value as MetricKey)}>
                {Object.values(METRICS).map((item) => <option key={item.key} value={item.key}>{item.shortLabel}</option>)}
              </select>
            </label>
            <SegmentedControl label="Режим значений" value={mode} options={VIEW_MODES} onChange={setMode} />
          </div>
          {comparison.isLoading ? <PageLoading label="Строю сравнение" /> : null}
          {comparison.error ? <ErrorState error={comparison.error} onRetry={() => comparison.refetch()} /> : null}
          {!comparison.isLoading && !comparison.error && selected.length === 0 ? <EmptyState title="Нечего сравнивать" description="Выберите хотя бы одну профессию слева." /> : null}
          {comparison.data?.length ? <ComparisonChart series={comparison.data} metric={metric} mode={mode} height={470} /> : null}
        </section>
      </div>
    </div>
  );
}
