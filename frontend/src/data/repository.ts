import type { DataRepository } from "./contracts";
import { DemoRepository } from "./demoRepository";
import { HttpRepository } from "./httpRepository";

export const dataMode = import.meta.env.MODE === "test" || import.meta.env.VITE_DATA_MODE === "demo" ? "demo" : "api";

export const repository: DataRepository = dataMode === "api"
  ? new HttpRepository(import.meta.env.VITE_API_BASE_URL ?? "")
  : new DemoRepository();
