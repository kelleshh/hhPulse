import { ArrowLeft, CirclePlay, RotateCcw } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { EmptyState, ErrorState, PageLoading } from "../components/ui/Feedback";
import { StatusBadge } from "../components/ui/StatusBadge";
import { useJobs, useProgress, useTriggerToday } from "../data/queries";

export function JobDetailPage() {
  const { jobId = "" } = useParams();
  const jobs = useJobs();
  const progress = useProgress(jobId);
  const trigger = useTriggerToday();
  const job = jobs.data?.find((item) => item.id === jobId);

  if (jobs.isLoading || progress.isLoading) return <PageLoading label="Загружаю состояние задачи" />;
  if (jobs.error || progress.error) return <ErrorState error={jobs.error ?? progress.error} onRetry={() => { jobs.refetch(); progress.refetch(); }} />;
  if (!job) return <EmptyState title="Задача не найдена" description="Вернитесь к списку и выберите существующую задачу." />;

  const run = progress.data;
  const percent = run && run.totalUnits > 0 ? (run.completedUnits / run.totalUnits) * 100 : 0;

  return (
    <div className="page">
      <Link className="back-link" to="/jobs"><ArrowLeft size={16} />Все задачи</Link>
      <header className="page-heading page-heading--split">
        <div><h1>{job.name}</h1><p>{job.roleSelectionMode === "all" ? "Все профессии HH" : `${job.roleIds.length} профессии`} · регион {job.regionIds.join(", ")} · {job.timezone}</p></div>
        <Button variant="primary" icon={run ? <RotateCcw size={17} /> : <CirclePlay size={17} />} disabled={!job.enabled || trigger.isPending} onClick={() => trigger.mutate(job.id)}>{run ? "Продолжить сегодня" : "Запустить сегодня"}</Button>
      </header>

      {!run ? <EmptyState title="Сегодняшний запуск ещё не создан" description="Запустите задачу вручную или дождитесь следующей проверки планировщика." /> : (
        <>
          <section className="run-detail">
            <div className="run-detail__head"><StatusBadge status={run.status} /><span>Run {run.runId}</span></div>
            <div className="run-detail__number"><strong>{run.completedUnits.toLocaleString("ru-RU")}</strong><span>из {run.totalUnits.toLocaleString("ru-RU")} запросов</span><b>{percent.toFixed(0)}%</b></div>
            <div className="progress-track progress-track--large"><span style={{ width: `${percent}%` }} /></div>
            <div className="run-detail__current"><span>Сейчас</span><strong>{run.currentRole ?? "Обработчик выполняет запрос"}</strong><small>{run.currentFilter ?? "Текущий фильтр будет доступен после расширения API прогресса"}</small></div>
          </section>
          <section className="run-stats">
            <div><span>Ожидают</span><strong>{run.pendingUnits.toLocaleString("ru-RU")}</strong></div>
            <div><span>В работе</span><strong>{run.runningUnits}</strong></div>
            <div><span>Ждут повтора</span><strong>{run.waitingRetryUnits}</strong></div>
            <div><span>Ошибки</span><strong>{run.failedUnits}</strong></div>
            <div><span>Всего попыток</span><strong>{run.totalAttempts.toLocaleString("ru-RU")}</strong></div>
          </section>
          <section className="event-log">
            <div className="section-heading"><h2>Последние события</h2><p>Журнал обновляется вместе с прогрессом.</p></div>
            <ol>
              <li><time>сейчас</time><span className="event-dot event-dot--active" /><div><strong>Обработка продолжается</strong><p>{run.runningUnits || 1} обработчика выполняют готовые запросы.</p></div></li>
              {run.waitingRetryUnits > 0 ? <li><time>недавно</time><span className="event-dot event-dot--warning" /><div><strong>Часть запросов ждёт повторения</strong><p>Данные уже завершённых запросов сохранены.</p></div></li> : null}
              <li><time>старт</time><span className="event-dot" /><div><strong>План создан и сохранён</strong><p>{run.totalUnits.toLocaleString("ru-RU")} единиц сбора готовы к выполнению.</p></div></li>
            </ol>
          </section>
        </>
      )}
    </div>
  );
}
