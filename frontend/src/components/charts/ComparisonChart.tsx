import { format, parseISO } from "date-fns";
import { ru } from "date-fns/locale";
import { useMemo, useState } from "react";
import {
  Area,
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { METRICS, formatMetric, transformSeries } from "../../domain/metrics";
import type { ChartGeometry, MarketSeries, MetricKey, ViewMode } from "../../domain/types";
import { Button } from "../ui/Button";

interface ComparisonChartProps {
  series: MarketSeries[];
  metric: MetricKey;
  mode: ViewMode;
  geometry?: ChartGeometry;
  height?: number;
}

interface ChartRow {
  date: string;
  [seriesId: string]: string | number | null;
}

export function ComparisonChart({ series, metric, mode, geometry = "line", height = 390 }: ComparisonChartProps) {
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
          <ComposedChart data={rows} margin={{ top: 12, right: 12, left: 0, bottom: 4 }} accessibilityLayer>
            <CartesianGrid stroke="rgb(190, 187, 169)" strokeDasharray="2 3" />
            <XAxis
              dataKey="date"
              tickFormatter={(value: string) => format(parseISO(value), "d MMM", { locale: ru })}
              tick={{ fill: "rgb(76, 76, 67)", fontSize: 11 }}
              axisLine={{ stroke: "rgb(125, 124, 112)" }}
              tickLine={false}
              minTickGap={36}
            />
            <YAxis
              tickFormatter={tickFormatter}
              tick={{ fill: "rgb(76, 76, 67)", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              width={58}
            />
            <Tooltip
              contentStyle={{ border: "1px solid rgb(87, 86, 76)", borderRadius: 0, boxShadow: "4px 4px 0 rgba(34,34,28,.16)", background: "rgb(244, 241, 220)" }}
              labelFormatter={(value) => format(parseISO(String(value)), "d MMMM yyyy", { locale: ru })}
              formatter={(value, name) => [formatMetric(Number(value), metric, mode), series.find((item) => item.id === name)?.label ?? name]}
            />
            <Legend formatter={(id) => series.find((item) => item.id === id)?.label ?? id} />
            {series.map((item) => {
              const common = { key: item.id, dataKey: item.id, name: item.id, isAnimationActive: false };
              if (geometry === "area") return <Area {...common} type="monotone" stroke={item.colour} fill={item.colour} fillOpacity={0.14} strokeWidth={2} connectNulls={false} />;
              if (geometry === "bars") return <Bar {...common} fill={item.colour} fillOpacity={0.76} maxBarSize={22} />;
              return (
                <Line
                  {...common}
                  type={geometry === "step" ? "stepAfter" : "monotone"}
                  stroke={geometry === "scatter" ? "transparent" : item.colour}
                  strokeWidth={2}
                  dot={geometry === "line-points" || geometry === "scatter" ? { r: geometry === "scatter" ? 3.5 : 2.5, fill: item.colour, strokeWidth: 0 } : false}
                  activeDot={{ r: 4, strokeWidth: 1, fill: item.colour }}
                  connectNulls={false}
                />
              );
            })}
          </ComposedChart>
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
