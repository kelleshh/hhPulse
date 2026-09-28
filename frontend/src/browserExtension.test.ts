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
  tree_complete?: boolean;
  roles?: Array<{ id: string; name: string; count: number }>;
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
    location: { href: `https://hh.ru/search/${target}?area=1` },
    setTimeout: (callback: () => void) => setTimeout(callback, 0),
    clearTimeout,
  }) as (target: string) => Promise<SearchResult>;
  return execute(target);
}

function page(heading: string, qa: string): void {
  document.title = "Поиск на hh.ru";
  document.body.innerHTML = `
    <div id="status"></div><input id="server"><input id="token">
    <button id="start"></button><button id="stop"></button>
    <h1 data-qa="${qa}">${heading}</h1>
    <button data-qa="header-search-filters-button">Фильтры</button>
  `;
}

function showVacancyFilters(childSetSize: number): void {
  document.body.insertAdjacentHTML("beforeend", `
    <button data-qa="search-drawer-filters-submit">Показать 9 вакансий</button>
    <div data-qa="search-filter-professional-role-trigger">Выберите из списка</div>
  `);
  document.querySelector<HTMLElement>('[data-qa="search-filter-professional-role-trigger"]')!
    .addEventListener("click", () => {
      document.body.insertAdjacentHTML("beforeend", `
        <div data-qa="search-filter-tree-selector-items">
          <div data-qa="tree-selector-container"><div role="tree">
            <div data-qa="tree-selector-item tree-selector-item-category-19">
              <div role="treeitem" aria-setsize="1"></div>
              <div data-qa="tree-selector-chevron tree-selector-chevron-category-19"></div>
              <span data-qa="cell-chevron">9</span>
            </div>
          </div></div>
        </div>
      `);
      const row = document.querySelector<HTMLElement>('[data-qa^="tree-selector-item "]')!;
      row.querySelector<HTMLElement>('[data-qa^="tree-selector-chevron"]')!
        .addEventListener("click", () => {
          row.dataset.qa = "tree-selector-item tree-selector-item-category-19 tree-selector-item-expanded";
          row.insertAdjacentHTML("afterend", `
            <div data-qa="tree-selector-item tree-selector-item-4 tree-selector-child-category-19">
              <div role="treeitem" aria-setsize="${childSetSize}"></div>
              <span data-qa="cell-text-content">Автомойщик</span>
              <span data-qa="cell-chevron">9</span>
            </div>
          `);
        });
    });
}

test("opens Filters and Specializations before reading vacancy professions", async () => {
  page("Найдено 9 вакансий", "title");
  const opener = document.querySelector<HTMLElement>('[data-qa="header-search-filters-button"]')!;
  opener.addEventListener("click", () => showVacancyFilters(1));

  const result = await extract("vacancy");

  expect(result.status).toBe("ok");
  expect(result.tree_complete).toBe(true);
  expect(result.roles).toEqual([{ id: "4", name: "Автомойщик", count: 9 }]);
});

test("does not publish a vacancy tree with missing virtualized children", async () => {
  page("Найдено 9 вакансий", "title");
  document.querySelector<HTMLElement>('[data-qa="header-search-filters-button"]')!
    .addEventListener("click", () => showVacancyFilters(2));

  const result = await extract("vacancy");

  expect(result.status).toBe("contract");
  expect(result.reason).toContain("пункты группы 19 просмотрены частично: 1/2");
});

test("opens Filters to read the full resume count from the same search", async () => {
  page("151 резюме", "search-title");
  document.body.insertAdjacentHTML("beforeend", "<p>1972 резюме скрыто</p>");
  document.querySelector<HTMLElement>('[data-qa="header-search-filters-button"]')!
    .addEventListener("click", () => {
      document.body.insertAdjacentHTML("beforeend", `
        <button data-qa="search-drawer-filters-submit">Показать 2123 резюме</button>
      `);
    });

  const result = await extract("resume");

  expect(result).toMatchObject({ status: "ok", total: 2123, visible: 151, hidden: 1972 });
});
