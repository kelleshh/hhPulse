import { AlertTriangle, DatabaseZap, LoaderCircle, RefreshCw } from "lucide-react";
import { Button } from "./Button";

export function PageLoading({ label = "Загружаю данные" }: { label?: string }) {
  return (
    <div className="feedback" role="status">
      <LoaderCircle className="feedback__spinner" size={24} aria-hidden="true" />
      <p>{label}</p>
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : "Неизвестная ошибка";
  return (
    <div className="feedback feedback--error" role="alert">
      <AlertTriangle size={24} aria-hidden="true" />
      <div>
        <strong>Данные не загрузились</strong>
        <p>{message}</p>
      </div>
      {onRetry ? <Button icon={<RefreshCw size={16} />} onClick={onRetry}>Повторить</Button> : null}
    </div>
  );
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="feedback feedback--empty">
      <DatabaseZap size={28} aria-hidden="true" />
      <div>
        <strong>{title}</strong>
        <p>{description}</p>
      </div>
    </div>
  );
}
