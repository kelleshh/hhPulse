import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./AppShell";
import { PageLoading } from "../components/ui/Feedback";

const AlertsPage = lazy(() => import("../pages/AlertsPage").then((module) => ({ default: module.AlertsPage })));
const ComparePage = lazy(() => import("../pages/ComparePage").then((module) => ({ default: module.ComparePage })));
const DashboardPage = lazy(() => import("../pages/DashboardPage").then((module) => ({ default: module.DashboardPage })));
const JobDetailPage = lazy(() => import("../pages/JobDetailPage").then((module) => ({ default: module.JobDetailPage })));
const JobsPage = lazy(() => import("../pages/JobsPage").then((module) => ({ default: module.JobsPage })));
const ProfessionConsolePage = lazy(() => import("../pages/ProfessionConsolePage").then((module) => ({ default: module.ProfessionConsolePage })));
const SettingsPage = lazy(() => import("../pages/SettingsPage").then((module) => ({ default: module.SettingsPage })));
const SnapshotPage = lazy(() => import("../pages/SnapshotPage").then((module) => ({ default: module.SnapshotPage })));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 20_000, retry: 1, refetchOnWindowFocus: false },
    mutations: { retry: 0 },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Suspense fallback={<PageLoading label="Открываю раздел" />}>
          <Routes>
            <Route element={<AppShell />}>
              <Route index element={<DashboardPage />} />
              <Route path="compare" element={<ComparePage />} />
              <Route path="snapshot" element={<SnapshotPage />} />
              <Route path="console" element={<ProfessionConsolePage />} />
              <Route path="jobs" element={<JobsPage />} />
              <Route path="jobs/:jobId" element={<JobDetailPage />} />
              <Route path="alerts" element={<AlertsPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
