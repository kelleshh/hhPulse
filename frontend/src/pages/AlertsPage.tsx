import { Check, CircleAlert, Info, ShieldAlert, TriangleAlert } from "lucide-react";
import { Button } from "../components/ui/Button";
import { EmptyState, ErrorState, PageLoading } from "../components/ui/Feedback";
import { useAlerts, useResolveAlert } from "../data/queries";
import type { AlertSeverity } from "../domain/types";

const ICONS = { critical: ShieldAlert, warning: TriangleAlert, info: Info };
const LABELS: Record<AlertSeverity, string> = { critical: "Критическое", warning: "Предупреждение", info: "Информация" };

export function AlertsPage() {
  const alerts = useAlerts();
  const resolve = useResolveAlert();

  return (
    <div className="page">
      <header className="page-heading"><h1>События</h1><p>Только состояния, которые влияют на полноту данных или требуют решения.</p></header>
      {alerts.isLoading ? <PageLoading label="Загружаю события" /> : null}
      {alerts.error ? <ErrorState error={alerts.error} onRetry={() => alerts.refetch()} /> : null}
      {alerts.data?.length === 0 ? <EmptyState title="Событий нет" description="Сбор работает штатно, вмешательство не требуется." /> : null}
      <div className="alerts-list">
        {alerts.data?.map((alert) => {
          const Icon = ICONS[alert.severity];
          return (
            <article key={alert.id} className={`alert-row alert-row--${alert.severity} ${alert.resolved ? "is-resolved" : ""}`}>
              <div className="alert-row__icon"><Icon size={21} /></div>
              <div className="alert-row__body">
                <div><span>{LABELS[alert.severity]}</span><time>{new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium", timeStyle: "short" }).format(new Date(alert.occurredAt))}</time></div>
                <h2>{alert.title}</h2>
                <p>{alert.description}</p>
                <small>{alert.jobName}</small>
              </div>
              <div className="alert-row__action">
                {alert.resolved ? <span className="resolved-label"><Check size={15} />Разобрано</span> : <Button size="small" onClick={() => resolve.mutate(alert.id)}>Отметить разобранным</Button>}
              </div>
            </article>
          );
        })}
      </div>
      <div className="alert-policy"><CircleAlert size={18} /><p><strong>HTML-контракт — терминальная ошибка.</strong> Такой запуск никогда не публикует частичный срез. Ответы 429 здесь считаются предупреждением: сбор замедляется и продолжается.</p></div>
    </div>
  );
}
