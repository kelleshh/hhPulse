import type { RunStatus } from "../../domain/types";

const STATUS_LABELS: Record<RunStatus, string> = {
  planned: "Запланирован",
  running: "Идёт сбор",
  waiting_source: "Ожидает HH",
  parser_broken: "Парсер остановлен",
  failed: "Ошибка",
  expired: "День пропущен",
  succeeded: "Опубликован",
};

export function StatusBadge({ status }: { status: RunStatus }) {
  return <span className={`status-badge status-badge--${status}`}>{STATUS_LABELS[status]}</span>;
}
