import type { DistributionItem } from "../../domain/types";

export function DistributionBars({ title, items }: { title: string; items: DistributionItem[] }) {
  return (
    <section className="distribution" aria-labelledby={`distribution-${title}`}>
      <h3 id={`distribution-${title}`}>{title}</h3>
      <div className="distribution__list">
        {items.map((item) => (
          <div className="distribution__row" key={item.id}>
            <div className="distribution__label">
              <span>{item.label}</span>
              <strong>{(item.share * 100).toLocaleString("ru-RU", { maximumFractionDigits: 1 })}%</strong>
            </div>
            <div className="distribution__track" aria-hidden="true">
              <span style={{ width: `${item.share * 100}%` }} />
            </div>
            <small>{item.value.toLocaleString("ru-RU")} вакансий</small>
          </div>
        ))}
      </div>
    </section>
  );
}
