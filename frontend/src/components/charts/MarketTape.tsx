import { format, parseISO } from "date-fns";
import { ru } from "date-fns/locale";
import type { ObservationDay, ObservationState } from "../../domain/types";

const LABELS: Record<ObservationState, string> = {
  published: "Срез опубликован",
  gap: "Компьютер был выключен или сбор не завершился",
  running: "Сегодняшний сбор идёт",
  parser_broken: "Сбор остановлен: изменился HTML",
};

export function MarketTape({ days, onSelect }: { days: ObservationDay[]; onSelect?: (day: ObservationDay) => void }) {
  return (
    <section className="market-tape" aria-labelledby="market-tape-title">
      <div className="market-tape__heading">
        <div>
          <h2 id="market-tape-title">Лента наблюдений</h2>
          <p>Последние 30 дней. Нажмите на день, чтобы открыть срез.</p>
        </div>
        <div className="market-tape__legend" aria-label="Состояния дней">
          <span><i className="tape-dot tape-dot--published" />Опубликовано</span>
          <span><i className="tape-dot tape-dot--gap" />Пропуск</span>
          <span><i className="tape-dot tape-dot--running" />Идёт сбор</span>
          <span><i className="tape-dot tape-dot--parser_broken" />Ошибка парсера</span>
        </div>
      </div>
      <div className="market-tape__track">
        {days.map((day, index) => {
          const title = `${format(parseISO(day.date), "d MMMM", { locale: ru })}: ${LABELS[day.state]}`;
          const showDate = index === 0 || index === days.length - 1 || (index % 7 === 0 && index < days.length - 3);
          return (
            <button
              key={day.date}
              className={`market-tape__day market-tape__day--${day.state}`}
              title={title}
              aria-label={title}
              disabled={day.state !== "published"}
              onClick={() => onSelect?.(day)}
            >
              <span className="market-tape__mark">
                {day.state === "running" && day.totalUnits ? (
                  <span style={{ width: `${Math.min(100, ((day.completedUnits ?? 0) / day.totalUnits) * 100)}%` }} />
                ) : null}
              </span>
              <small>{showDate ? format(parseISO(day.date), "d MMM", { locale: ru }) : ""}</small>
            </button>
          );
        })}
      </div>
    </section>
  );
}
