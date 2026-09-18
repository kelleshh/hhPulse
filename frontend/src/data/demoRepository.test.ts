import { describe, expect, it } from "vitest";
import { DemoRepository } from "./demoRepository";

describe("DemoRepository", () => {
  it("persists created jobs and enable state", async () => {
    const repository = new DemoRepository();
    const created = await repository.createJob({
      name: "Тестовый рынок",
      regionIds: ["1"],
      roleSelectionMode: "selected",
      roleIds: ["96"],
      includeExperienceStrata: true,
      maxConcurrency: 2,
      maxRps: 0.5,
      userAgentMode: "shared",
      timezone: "Europe/Moscow",
      enabled: true,
    });

    await repository.setJobEnabled(created.id, false);
    const stored = (await repository.listJobs()).find((job) => job.id === created.id);

    expect(stored?.enabled).toBe(false);
    expect(stored?.methodologyVersion).toBe("hh-index-daily-v1");
  });

  it("returns gaps as nulls instead of zeroes", async () => {
    const repository = new DemoRepository();
    const series = await repository.getComparison({
      comparisonMode: "roles",
      roleIds: ["96"],
      metric: "vacancies",
      experience: "any",
      experienceStrata: [],
      dateFrom: "2026-08-01",
      dateTo: "2026-09-18",
    });

    expect(series[0].points.some((point) => point.value === null)).toBe(true);
  });
});
