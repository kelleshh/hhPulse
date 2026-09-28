import {
  Bell,
  ChartNoAxesCombined,
  Database,
  GitCompareArrows,
  LayoutDashboard,
  PanelsTopLeft,
  Settings,
  SlidersHorizontal,
} from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { useAlerts } from "../data/queries";
import { dataMode } from "../data/repository";

const navigation = [
  { to: "/", label: "Обзор", icon: LayoutDashboard, end: true },
  { to: "/compare", label: "Сравнение", icon: GitCompareArrows },
  { to: "/snapshot", label: "Срез рынка", icon: ChartNoAxesCombined },
  { to: "/console", label: "Пульт профессий", icon: PanelsTopLeft },
  { to: "/jobs", label: "Сбор данных", icon: Database },
  { to: "/alerts", label: "События", icon: Bell },
  { to: "/settings", label: "Настройки", icon: Settings },
];

export function AppShell() {
  const alerts = useAlerts();
  const unresolved = alerts.data?.filter((alert) => !alert.resolved).length ?? 0;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand__mark" aria-hidden="true"><i /><i /><i /></span>
          <span><strong>hhPulse</strong><small>рынок труда</small></span>
        </div>
        <nav className="primary-nav" aria-label="Основная навигация">
          {navigation.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end}>
              <Icon size={19} strokeWidth={1.8} />
              <span>{label}</span>
              {to === "/alerts" && unresolved > 0 ? <b aria-label={`${unresolved} непросмотренных событий`}>{unresolved}</b> : null}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar__source">
          <SlidersHorizontal size={17} aria-hidden="true" />
          <span>
            <small>Источник</small>
            <strong>{dataMode === "demo" ? "Демонстрационные данные" : "Локальный API"}</strong>
          </span>
        </div>
      </aside>
      <div className="app-main">
        <header className="topbar">
          <div className="topbar__source-state">
            <span className="source-light" aria-hidden="true" />
            <span>
              <strong>{dataMode === "demo" ? "Демонстрационный режим" : "Режим реальных данных"}</strong>
              <small>{dataMode === "demo" ? "запросы к HH не выполняются" : "SQLite · HH API · журнал сбора"}</small>
            </span>
          </div>
          <time dateTime={new Date().toISOString()}>
            {new Intl.DateTimeFormat("ru-RU", { weekday: "long", day: "numeric", month: "long" }).format(new Date())}
          </time>
        </header>
        <main className="page-container"><Outlet /></main>
      </div>
    </div>
  );
}
