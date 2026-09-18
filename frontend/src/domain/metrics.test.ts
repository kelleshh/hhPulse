import { describe, expect, it } from "vitest";
import { formatMetric, transformSeries } from "./metrics";

describe("transformSeries", () => {
  it("normalises against the first available observation", () => {
    expect(transformSeries([null, 20, 25, 10], "index")).toEqual([null, 100, 125, 50]);
  });

  it("keeps honest gaps when calculating relative change", () => {
    expect(transformSeries([10, null, 12], "change")).toEqual([0, null, 20]);
  });

  it("does not invent ratios when the base is zero", () => {
    expect(transformSeries([0, 10], "index")).toEqual([null, null]);
  });
});

describe("formatMetric", () => {
  it("formats shares as percentages only in absolute mode", () => {
    expect(formatMetric(0.428, "lowResponseShare", "absolute")).toBe("42,8%");
    expect(formatMetric(12.4, "lowResponseShare", "change")).toBe("12,4%");
  });
});
