import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { AppSettings, CreateJobInput, MetricKey } from "../domain/types";
import type { ComparisonRequest } from "./contracts";
import { repository } from "./repository";

export const queryKeys = {
  jobs: ["jobs"] as const,
  progress: (jobId: string) => ["progress", jobId] as const,
  roles: ["roles"] as const,
  overview: (metric: MetricKey) => ["overview", metric] as const,
  comparison: (request: ComparisonRequest) => ["comparison", request] as const,
  snapshot: (date: string, roleId: string) => ["snapshot", date, roleId] as const,
  alerts: ["alerts"] as const,
  settings: ["settings"] as const,
};

export const useJobs = () => useQuery({ queryKey: queryKeys.jobs, queryFn: () => repository.listJobs() });

export const useRoles = () => useQuery({ queryKey: queryKeys.roles, queryFn: () => repository.listRoles(), staleTime: 3_600_000 });

export const useProgress = (jobId: string, enabled = true) => useQuery({
  queryKey: queryKeys.progress(jobId),
  queryFn: () => repository.getTodayProgress(jobId),
  enabled: enabled && Boolean(jobId),
  refetchInterval: 5_000,
});

export const useOverview = (metric: MetricKey) => useQuery({
  queryKey: queryKeys.overview(metric),
  queryFn: () => repository.getOverview(metric),
});

export const useComparison = (request: ComparisonRequest) => useQuery({
  queryKey: queryKeys.comparison(request),
  queryFn: () => repository.getComparison(request),
  enabled: request.roleIds.length > 0,
});

export const useSnapshot = (date: string, roleId: string) => useQuery({
  queryKey: queryKeys.snapshot(date, roleId),
  queryFn: () => repository.getSnapshot(date, roleId),
  enabled: Boolean(date && roleId),
});

export const useAlerts = () => useQuery({ queryKey: queryKeys.alerts, queryFn: () => repository.listAlerts() });
export const useSettings = () => useQuery({ queryKey: queryKeys.settings, queryFn: () => repository.getSettings() });

export function useCreateJob() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateJobInput) => repository.createJob(input),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.jobs }),
  });
}

export function useSetJobEnabled() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ jobId, enabled }: { jobId: string; enabled: boolean }) => repository.setJobEnabled(jobId, enabled),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.jobs }),
  });
}

export function useTriggerToday() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => repository.triggerToday(jobId),
    onSuccess: (_, jobId) => client.invalidateQueries({ queryKey: queryKeys.progress(jobId) }),
  });
}

export function useResolveAlert() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (alertId: string) => repository.resolveAlert(alertId),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.alerts }),
  });
}

export function useSaveSettings() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (settings: AppSettings) => repository.saveSettings(settings),
    onSuccess: (settings) => client.setQueryData(queryKeys.settings, settings),
  });
}
