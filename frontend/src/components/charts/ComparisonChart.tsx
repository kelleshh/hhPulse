import { format, parseISO } from "date-fns";
import { ru } from "date-fns/locale";
import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { METRICS, formatMetric, transformSeries } from "../../domain/metrics";
import type { MarketSeries, MetricKey, ViewMode } from "../../domain/types";
import { Button } from "../ui/Button";

interface ComparisonChartProps {
  series: MarketSeries[];
  metric: MetricKey;
  mode: ViewMode;
  height?: number;
}

interface ChartRow {
  date: string;
  [seriesId: string]: string | number | null;
}

export function ComparisonChart({ series, metric, mode, height = 390 }: ComparisonChartProps) {
  const [showTable, setShowTable] = useState(false);
  const rows = useMemo(() => {
    const byDate = new Map<string, ChartRow>();
    series.forEach((item) => {
      const values = transformSeries(item.points.map((point) => point.value), mode);
      item.points.forEach((point, index) => {
        const row = byDate.get(point.date) ?? { date: point.date };
        row[item.id] = values[index] ?? null;
        byDate.set(point.date, row);
      });
    });
    return [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
  }, [series, mode]);

  const tickFormatter = (value: number) => {
    if (mode !== "absolute") return `${Math.round(value)}${mode === "change" ? "%" : ""}`;
    if (METRICS[metric].unit === "percent") return `${Math.round(value * 100)}%`;
    return Intl.NumberFormat("ru-RU", { notation: value >= 10_000 ? "compact" : "standard", maximumFractionDigits: 1 }).format(value);
  };

  return (
    <div className="comparison-chart">
      <div className="chart-frame" style={{ height }} aria-label={`График: ${METRICS[metric].label}`}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 12, right: 12, left: 0, bottom: 4 }} accessibilityLayer>
            <CartesianGrid stroke="#DDE4EF" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={(value: string) => format(parseISO(value), "d MMM", { locale: ru })}
              tick={{ fill: "#66728A", fontSize: 12 }}
              axisLine={{ stroke: "#BAC5D6" }}
              tickLine={false}
              minTickGap={36}
            />
            <YAxis
              tickFormatter={tickFormatter}
              tick={{ fill: "#66728A", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
              width={58}
            />
            <Tooltip
              contentStyle={{ border: "1px solid #BAC5D6", borderRadius: 10, boxShadow: "0 12px 34px rgba(24,35,59,.13)" }}
              labelFormatter={(value) => format(parseISO(String(value)), "d MMMM yyyy", { locale: ru })}
              formatter={(value, name) => [formatMetric(Number(value), metric, mode), series.find((item) => item.id === name)?.label ?? name]}
            />
            <Legend formatter={(id) => series.find((item) => item.id === id)?.label ?? id} />
            {series.map((item) => (
              <Line
                key={item.id}
                type="monotone"
                dataKey={item.id}
                name={item.id}
                stroke={item.colour}
                strokeWidth={2.5}
                dot={false}
                activeDot={{ r: 4, strokeWidth: 2, fill: "#FFFFFF" }}
                connectNulls={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="chart-foot">
        <p>{METRICS[metric].description}. Разрывы линии означают отсутствие опубликованного среза.</p>
        <Button variant="quiet" size="small" onClick={() => setShowTable((value) => !value)}>
          {showTable ? "Скрыть таблицу" : "Показать таблицу"}
        </Button>
      </div>
      {showTable ? (
        <div className="table-scroll">
          <table className="data-table data-table--compact">
            <thead>
              <tr>
                <th>Дата</th>
                {series.map((item) => <th key={item.id}>{item.label}</th>)}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.date}>
                  <td>{format(parseISO(row.date), "d MMM yyyy", { locale: ru })}</td>
                  {series.map((item) => <td key={item.id}>{formatMetric(Number.isFinite(row[item.id]) ? Number(row[item.id]) : null, metric, mode)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
