import { ArrowLeft, CirclePlay, Radio, RotateCcw } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { EmptyState, ErrorState, PageLoading } from "../components/ui/Feedback";
import { StatusBadge } from "../components/ui/StatusBadge";
import { useJobs, useProgress, useRunEvents, useTriggerToday } from "../data/queries";

const eventLabels: Record<string, string> = {
  run_started: "План запуска создан",
  workers_recovered: "Незавершённые обработчики восстановлены",
  unit_started: "Запрос отправлен в обработку",
  retry_scheduled: "Повтор запроса запланирован",
  unit_completed: "Наблюдение сохранено",
  parser_broken: "Контракт ответа изменился",
  run_failed: "Запуск остановлен с ошибкой",
  run_expired: "Временное окно запуска закончилось",
  run_published: "Дневной срез опубликован",
  run_reopened: "Запуск продолжен после исправления парсера",
};

export function JobDetailPage() {
  const { jobId = "" } = useParams();
  const jobs = useJobs();
  const progress = useProgress(jobId);
  const events = useRunEvents(jobId);
  const trigger = useTriggerToday();
  const job = jobs.data?.find((item) => item.id === jobId);

  if (jobs.isLoading || progress.isLoading) return <PageLoading label="Загружаю состояние задачи" />;
  if (jobs.error || progress.error) return <ErrorState error={jobs.error ?? progress.error} onRetry={() => { void jobs.refetch(); void progress.refetch(); }} />;
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
            <div className="section-heading section-heading--split"><div><h2>Живой журнал сбора</h2><p>Транзакционные события из SQLite, автоматическое обновление каждые 2 секунды.</p></div><span className="live-indicator"><Radio size={14} /> LIVE · {events.data?.length ?? 0}</span></div>
            {events.error ? <ErrorState error={events.error} onRetry={() => events.refetch()} /> : null}
            {!events.error && events.data?.length ? (
              <ol className="event-log__stream">
                {events.data.map((event) => (
                  <li key={event.id} className={`event-log__${event.level}`}>
                    <time dateTime={event.occurredAt}>{new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date(event.occurredAt))}</time>
                    <span className={`event-dot event-dot--${event.level}`} />
                    <div><strong>{eventLabels[event.eventType] ?? event.eventType}</strong><p>{event.message}</p></div>
                    <code>{String(event.id).padStart(6, "0")}</code>
                  </li>
                ))}
              </ol>
            ) : !events.error ? <div className="event-log__empty">Журнал создан. Ожидаю первое событие обработчика…</div> : null}
          </section>
        </>
      )}
    </div>
  );
}
