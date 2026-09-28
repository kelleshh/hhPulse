import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { runInNewContext } from "node:vm";

import { beforeAll, expect, test } from "vitest";

const runnerSource = readFileSync(resolve(process.cwd(), "../browser-extension/runner.js"), "utf8");

type SearchResult = {
  status: string;
  reason?: string;
  total?: number;
  visible?: number;
  hidden?: number;
};

beforeAll(() => {
  // jsdom does not implement the rendered innerText used by Chrome.
  Object.defineProperty(HTMLElement.prototype, "innerText", {
    configurable: true,
    get() { return this.textContent; },
  });
});

async function extract(target: "vacancy" | "resume"): Promise<SearchResult> {
  const execute = runInNewContext(`${runnerSource}\nextractSearch`, {
    document,
    location: { href: `https://hh.ru/search/${target}?area=1&professional_role=96` },
    setTimeout: (callback: () => void) => setTimeout(callback, 0),
    clearTimeout,
  }) as (target: string) => Promise<SearchResult>;
  return execute(target);
}

function page(heading: string, qa: string): HTMLButtonElement {
  document.title = "Поиск на hh.ru";
  document.body.innerHTML = `
    <div id="status"></div><input id="server"><input id="token">
    <button id="start"></button><button id="stop"></button>
    <h1 data-qa="${qa}">${heading}</h1>
    <button data-qa="header-search-filters-button">Фильтры</button>
  `;
  return document.querySelector<HTMLButtonElement>('[data-qa="header-search-filters-button"]')!;
}

test("reads the vacancy count from its own search URL without opening filters", async () => {
  const filters = page("Найдено 2 064 вакансии", "title");
  let clicks = 0;
  filters.addEventListener("click", () => { clicks += 1; });

  expect(await extract("vacancy")).toMatchObject({ status: "ok", total: 2064 });
  expect(clicks).toBe(0);
});

test("sums visible and hidden resumes from the same search without opening filters", async () => {
  const filters = page("151 резюме", "search-title");
  let clicks = 0;
  filters.addEventListener("click", () => { clicks += 1; });
  document.body.insertAdjacentHTML("beforeend", "<p>У вас непроверенная регистрация — 1 972 резюме скрыто.</p>");

  expect(await extract("resume")).toMatchObject({
    status: "ok", total: 2123, visible: 151, hidden: 1972,
  });
  expect(clicks).toBe(0);
});

test("zero hidden resumes are counted when there is no hidden banner", async () => {
  page("7 резюме", "search-title");
  expect(await extract("resume")).toMatchObject({
    status: "ok", total: 7, visible: 7, hidden: 0,
  });
});

test("does not silently ignore an unreadable hidden-resume banner", async () => {
  page("7 резюме", "search-title");
  document.body.insertAdjacentHTML("beforeend", "<p>Много резюме скрыто.</p>");
  expect(await extract("resume")).toMatchObject({ status: "contract" });
});

test("refuses an unrecognized vacancy count", async () => {
  page("Поиск вакансий", "title");
  expect(await extract("vacancy")).toMatchObject({ status: "contract" });
});
