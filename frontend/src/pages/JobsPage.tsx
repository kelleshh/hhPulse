import { CirclePlay, Plus, Settings2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { CreateJobDialog } from "../components/jobs/CreateJobDialog";
import { Button } from "../components/ui/Button";
import { EmptyState, ErrorState, PageLoading } from "../components/ui/Feedback";
import { useJobs, useSetJobEnabled, useTriggerToday } from "../data/queries";

export function JobsPage() {
  const [createOpen, setCreateOpen] = useState(false);
  const jobs = useJobs();
  const setEnabled = useSetJobEnabled();
  const trigger = useTriggerToday();

  return (
    <div className="page">
      <header className="page-heading page-heading--split">
        <div><h1>Сбор данных</h1><p>Задачи, которые ежедневно создают полный срез рынка и переживают перезапуск.</p></div>
        <Button variant="primary" icon={<Plus size={17} />} onClick={() => setCreateOpen(true)}>Новая задача</Button>
      </header>
      {jobs.isLoading ? <PageLoading label="Загружаю задачи" /> : null}
      {jobs.error ? <ErrorState error={jobs.error} onRetry={() => jobs.refetch()} /> : null}
      {jobs.data?.length === 0 ? <EmptyState title="Задач пока нет" description="Создайте первую задачу, чтобы начать ежедневные наблюдения." /> : null}
      {jobs.data?.length ? (
        <div className="jobs-list">
          {jobs.data.map((job) => (
            <article className="job-row" key={job.id}>
              <div className="job-row__state"><span className={job.enabled ? "source-light" : "source-light source-light--off"} /><span><strong>{job.enabled ? "Включена" : "На паузе"}</strong><small>{job.timezone}</small></span></div>
              <div className="job-row__name"><Link to={`/jobs/${job.id}`}>{job.name}</Link><small>{job.roleSelectionMode === "all" ? "Все профессии" : `${job.roleIds.length} выбранных профессии`} · {job.regionIds.length} регион</small></div>
              <dl className="job-row__limits"><div><dt>Параллельно</dt><dd>{job.maxConcurrency}</dd></div><div><dt>Лимит</dt><dd>{job.maxRps} запр./с</dd></div><div><dt>Опыт</dt><dd>{job.includeExperienceStrata ? "5 страт" : "общий"}</dd></div></dl>
              <div className="job-row__actions">
                <Button size="small" icon={<CirclePlay size={16} />} disabled={!job.enabled || trigger.isPending} onClick={() => trigger.mutate(job.id)}>Запустить</Button>
                <button className="switch" role="switch" aria-checked={job.enabled} aria-label={`${job.enabled ? "Остановить" : "Включить"} задачу ${job.name}`} onClick={() => setEnabled.mutate({ jobId: job.id, enabled: !job.enabled })}><span /></button>
                <Link className="icon-button" aria-label={`Открыть настройки ${job.name}`} to={`/jobs/${job.id}`}><Settings2 size={18} /></Link>
              </div>
            </article>
          ))}
        </div>
      ) : null}
      {(trigger.isSuccess || trigger.error) ? <div className={`toast ${trigger.error ? "toast--error" : ""}`} role="status">{trigger.error ? trigger.error.message : trigger.data ? "Запуск принят" : "Задача уже выполняется"}</div> : null}
      <CreateJobDialog open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  );
}
