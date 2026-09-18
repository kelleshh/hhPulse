import type { DataRepository } from "./contracts";
import { DemoRepository } from "./demoRepository";
import { HttpRepository } from "./httpRepository";

export const dataMode = import.meta.env.VITE_DATA_MODE === "api" ? "api" : "demo";

export const repository: DataRepository = dataMode === "api"
  ? new HttpRepository(import.meta.env.VITE_API_BASE_URL ?? "")
  : new DemoRepository();
