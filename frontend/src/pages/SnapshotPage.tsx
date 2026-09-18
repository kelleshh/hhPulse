import { CalendarDays, Info } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { DistributionBars } from "../components/charts/DistributionBars";
import { EmptyState, ErrorState, PageLoading } from "../components/ui/Feedback";
import { useRoles, useSnapshot } from "../data/queries";
import { DataSourceError } from "../data/contracts";

const today = new Date();
const todayIso = today.toISOString().slice(0, 10);

export function SnapshotPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const roles = useRoles();
  const [date, setDate] = useState(searchParams.get("date") ?? todayIso);
  const [roleId, setRoleId] = useState(searchParams.get("role") ?? "");
  const snapshot = useSnapshot(date, roleId);

  useEffect(() => {
    if (roleId || !roles.data?.length) return;
    setRoleId(roles.data[0].id);
  }, [roleId, roles.data]);

  return (
    <div className="page">
      <header className="page-heading page-heading--split">
        <div>
          <h1>Срез рынка</h1>
          <p>Структура одной профессии в конкретный опубликованный день.</p>
        </div>
        <div className="snapshot-selectors">
          <label className="field field--inline"><span>Профессия</span><select value={roleId} onChange={(event) => { const value = event.target.value; setRoleId(value); setSearchParams({ date, role: value }); }}>{roles.data?.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}</select></label>
          <label className="field field--inline"><span>Дата</span><div className="input-with-icon"><CalendarDays size={16} /><input type="date" value={date} max={todayIso} onChange={(event) => { const value = event.target.value; setDate(value); setSearchParams({ date: value, role: roleId }); }} /></div></label>
        </div>
      </header>

      {snapshot.isLoading ? <PageLoading label="Загружаю срез рынка" /> : null}
      {snapshot.error instanceof DataSourceError && snapshot.error.status === 404 ? <EmptyState title="На эту дату срез не опубликован" description="Запустите сбор и дождитесь его завершения либо выберите день, который уже опубликован." /> : null}
      {snapshot.error && !(snapshot.error instanceof DataSourceError && snapshot.error.status === 404) ? <ErrorState error={snapshot.error} onRetry={() => snapshot.refetch()} /> : null}
      {snapshot.data ? <SnapshotContent data={snapshot.data} /> : null}
    </div>
  );
}

function SnapshotContent({ data }: { data: NonNullable<ReturnType<typeof useSnapshot>["data"]> }) {
  return (
    <>
      <section className="snapshot-title">
        <div><h2>{data.roleName}</h2><p>Москва · любой опыт</p></div>
        <span className="method-note"><Info size={16} />Методология hh-index-daily-v1</span>
      </section>
      <section className="snapshot-measures snapshot-measures--extended" aria-label="Основные показатели">
        <div><span>Вакансии</span><strong>{data.vacancies.toLocaleString("ru-RU")}</strong><small>активные объявления</small></div>
        <div><span>Резюме</span><strong>{data.resumes.toLocaleString("ru-RU")}</strong><small>активны за 60 дней</small></div>
        <div className="snapshot-measures__focus"><span>hh-индекс</span><strong>{data.hhIndex.toLocaleString("ru-RU", { maximumFractionDigits: 1 })}</strong><small>резюме на вакансию</small></div>
        <div><span>Менее 10 откликов</span><strong>{(data.lowResponseShare * 100).toFixed(1)}%</strong><small>от всех вакансий</small></div>
        <div><span>Зарплата указана</span><strong>{(data.salaryVisibleShare * 100).toFixed(1)}%</strong><small>от всех вакансий</small></div>
        <div><span>Удалённая работа</span><strong>{data.remoteShare === null ? "—" : `${(data.remoteShare * 100).toFixed(1)}%`}</strong><small>от всех вакансий</small></div>
        <div><span>Гибридный формат</span><strong>{data.hybridShare === null ? "—" : `${(data.hybridShare * 100).toFixed(1)}%`}</strong><small>от всех вакансий</small></div>
        <div><span>Без опыта</span><strong>{data.noExperienceShare === null ? "—" : `${(data.noExperienceShare * 100).toFixed(1)}%`}</strong><small>от всех вакансий</small></div>
        <div><span>Высшее образование</span><strong>{data.higherEducationShare === null ? "—" : `${(data.higherEducationShare * 100).toFixed(1)}%`}</strong><small>от всех вакансий</small></div>
      </section>
      <div className="distribution-grid">
        <DistributionBars title="Опыт" items={data.distributions.experience} />
        <DistributionBars title="Формат работы" items={data.distributions.workFormat} />
        <DistributionBars title="График" items={data.distributions.schedule} />
        <DistributionBars title="Занятость" items={data.distributions.employment} />
        <DistributionBars title="Образование" items={data.distributions.education} />
        <DistributionBars title="Метки HH" items={data.distributions.labels} />
      </div>
      <p className="snapshot-footnote">Суммы в распределениях могут отличаться от общего числа вакансий: один ответ HH может относиться к нескольким вариантам фасета.</p>
    </>
  );
}
