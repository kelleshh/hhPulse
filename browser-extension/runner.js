const statusLine = document.getElementById("status");
const serverInput = document.getElementById("server");
const tokenInput = document.getElementById("token");
let running = false;
let searchTabId = null;

function status(message) { statusLine.textContent = message; }
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function api(path, options = {}) {
  const response = await fetch(`${serverInput.value.replace(/\/$/, "")}/api/v1/browser/${path}`, {
    ...options,
    headers: { "X-HHPULSE-BROWSER-TOKEN": tokenInput.value, ...options.headers },
  });
  if (!response.ok) throw new Error(`Локальный сервер ответил HTTP ${response.status}`);
  return response.json();
}

async function search(command) {
  if (!searchTabId || !(await chrome.tabs.get(searchTabId).catch(() => null))) {
    searchTabId = (await chrome.tabs.create({ url: "about:blank", active: true })).id;
  }
  status(`Поиск ${command.target}: ${command.url}`);
  const loaded = new Promise((resolve, reject) => {
    const timeout = setTimeout(() => { chrome.tabs.onUpdated.removeListener(listener); reject(new Error("Страница HH не загрузилась за 90 секунд")); }, 90000);
    function listener(tabId, changeInfo) {
      if (tabId === searchTabId && changeInfo.status === "complete") {
        clearTimeout(timeout); chrome.tabs.onUpdated.removeListener(listener); resolve();
      }
    }
    chrome.tabs.onUpdated.addListener(listener);
  });
  await chrome.tabs.update(searchTabId, { url: command.url, active: true });
  await loaded;
  const [{ result }] = await chrome.scripting.executeScript({
    target: { tabId: searchTabId }, func: extractSearch, args: [command.target],
  });
  return result;
}

// This function runs inside hh.ru. It returns counts only, never candidate cards or cookies.
async function extractSearch(target) {
  const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const headingSelector = target === "resume" ? '[data-qa="search-title"]' : 'h1[data-qa="title"]';
  for (let attempt = 0; attempt < 100 && !document.querySelector(headingSelector); attempt++) {
    if (/captcha|капча|access denied|too many requests/i.test(document.title)) break;
    await pause(150);
  }
  await pause(250);
  const count = (raw) => {
    const digits = (raw || "").replace(/[^\d]/g, "");
    return digits ? Number(digits) : null;
  };
  const text = document.body.innerText;
  const title = document.title.toLowerCase();
  if (/captcha|капча|access denied|too many requests|слишком много запросов/i.test(title) ||
      /^(доступ ограничен|проверка безопасности|too many requests)/i.test(text.trim().slice(0, 200))) {
    return { status: "blocked", reason: "страница защиты или ограничения", url: location.href };
  }
  if (/войти|авторизац/i.test(title) && !document.querySelector('[data-qa="title"], [data-qa="search-title"]')) {
    return { status: "auth", reason: "нужно войти в аккаунт работодателя", url: location.href };
  }
  // The submit button and profession selector are mounted only after opening Filters.
  async function openFilters(requiredSelector) {
    const submitSelector = '[data-qa="search-drawer-filters-submit"]';
    if (!document.querySelector(submitSelector)) {
      const opener = document.querySelector('[data-qa="header-search-filters-button"]');
      if (!opener) return null;
      opener.click();
    }
    for (let attempt = 0; attempt < 100; attempt++) {
      const submit = document.querySelector(submitSelector);
      const required = requiredSelector ? document.querySelector(requiredSelector) : true;
      if (submit && required) return { submit, required };
      await pause(100);
    }
    return null;
  }
  const filters = await openFilters(
    target === "vacancy" ? '[data-qa="search-filter-professional-role-trigger"]' : null,
  );
  if (!filters) {
    return { status: "contract", reason: "панель фильтров или поле «Специализации» не открылось", url: location.href };
  }
  if (target === "resume") {
    const heading = document.querySelector('[data-qa="search-title"]');
    const total = count(filters.submit.innerText.match(/[\d\s\u00a0\u202f]+(?=\s*резюм)/i)?.[0]);
    const visible = count(heading?.innerText.match(/[\d\s\u00a0\u202f]+(?=\s*резюм)/i)?.[0]) ??
      (/ничего не найдено|резюме не найден/i.test(heading?.innerText || "") ? 0 : null);
    const hiddenMatch = text.match(/([\d\s\u00a0\u202f]+)\s+резюме\s+скрыт/i);
    const hidden = hiddenMatch ? count(hiddenMatch[1]) : 0;
    if (total === null || visible === null || hidden === null) {
      return { status: "contract", reason: "счётчики резюме не найдены", url: location.href };
    }
    return { status: "ok", url: location.href, total, visible, hidden };
  }
  const heading = document.querySelector('h1[data-qa="title"]');
  const total = count(heading?.innerText.match(/[\d\s\u00a0\u202f]+(?=\s*ваканси)/i)?.[0]) ??
    (/ничего не найдено|вакансии не найдены/i.test(heading?.innerText || "") ? 0 : null);
  if (total === null) return { status: "contract", reason: "счётчик вакансий не найден", url: location.href };
  const pending = count(filters.submit.innerText.match(/[\d\s\u00a0\u202f]+(?=\s*ваканси)/i)?.[0]);
  if (pending !== null && pending !== total) {
    return { status: "contract", reason: "счётчики выдачи и текущих фильтров не совпали", url: location.href };
  }
  if (total === 0) return { status: "ok", url: location.href, total, roles: [], tree_complete: true };
  filters.required.click();
  let modal = null;
  let tree = null;
  for (let n = 0; n < 100; n++) {
    modal = document.querySelector('[data-qa="search-filter-tree-selector-items"]');
    tree = modal?.querySelector('[role="tree"]');
    if (tree) break;
    await pause(100);
  }
  if (!modal) return { status: "contract", reason: "дерево профессий не открылось", url: location.href };
  if (!tree) return { status: "contract", reason: "виртуальный список не найден", url: location.href };
  const scroller = modal.querySelector('[data-qa="tree-selector-container"]');
  if (!scroller || !scroller.contains(tree)) {
    return { status: "contract", reason: "прокручиваемый список профессий не найден", url: location.href };
  }
  const categories = new Set();
  const expanded = new Set();
  const roles = new Map();
  const expectedChildren = new Map();
  const observedChildren = new Map();
  const categoryCounts = new Map();
  let categoryTotal = 0;
  function inspect(expand) {
    let clicked = false;
    for (const row of tree.querySelectorAll('[data-qa^="tree-selector-item "]')) {
      const qa = row.getAttribute("data-qa") || "";
      const category = qa.match(/tree-selector-item-category-(\d+)/);
      if (category) {
        categories.add(category[1]);
        categoryTotal = Math.max(categoryTotal, Number(row.querySelector('[role="treeitem"]')?.getAttribute("aria-setsize") || 0));
        const rawCount = row.querySelector('[data-qa="cell-chevron"]')?.textContent?.trim();
        if (!rawCount || !/^\d[\d\s\u00a0\u202f]*$/.test(rawCount)) {
          throw new Error(`Нет числа для группы ${category[1]}`);
        }
        categoryCounts.set(category[1], count(rawCount));
        if (qa.includes("tree-selector-item-expanded")) expanded.add(category[1]);
        else if (expand) {
          const chevron = row.querySelector('[data-qa^="tree-selector-chevron"]');
          if (chevron) { chevron.click(); clicked = true; break; }
        }
      }
      const child = qa.match(/(?:^| )tree-selector-item-(\d+)(?: |$)/);
      const parent = qa.match(/tree-selector-child-category-(\d+)/);
      if (child && parent) {
        const name = row.querySelector('[data-qa="cell-text-content"]')?.textContent?.trim();
        const rawCount = row.querySelector('[data-qa="cell-chevron"]')?.textContent?.trim();
        const amount = count(rawCount);
        if (!name || !rawCount || !/^\d[\d\s\u00a0\u202f]*$/.test(rawCount)) {
          throw new Error(`Нет числа для профессии ${child[1]}`);
        }
        const size = Number(row.querySelector('[role="treeitem"]')?.getAttribute("aria-setsize"));
        if (!Number.isSafeInteger(size) || size < 1 ||
            (expectedChildren.has(parent[1]) && expectedChildren.get(parent[1]) !== size)) {
          throw new Error(`Неверный размер группы ${parent[1]}`);
        }
        expectedChildren.set(parent[1], size);
        if (!observedChildren.has(parent[1])) observedChildren.set(parent[1], new Set());
        observedChildren.get(parent[1]).add(child[1]);
        const previous = roles.get(child[1]);
        if (previous && (previous.count !== amount || previous.name !== name)) throw new Error(`Разные числа для профессии ${child[1]}`);
        roles.set(child[1], { id: child[1], name, count: amount });
      }
    }
    return clicked;
  }
  try {
    // Expand all 27-ish groups. Scrolling overlaps to cover virtualized rows.
    for (let pass = 0; pass < 40 && (categoryTotal === 0 || expanded.size < categoryTotal); pass++) {
      scroller.scrollTop = 0; await pause(80);
      let position = 0;
      for (let step = 0; step < 3000; step++) {
        if (inspect(true)) { await pause(80); continue; }
        const next = Math.min(scroller.scrollHeight - scroller.clientHeight, position + Math.max(80, scroller.clientHeight / 2));
        if (next <= position + 1) break;
        scroller.scrollTop = next; position = next; await pause(35);
      }
    }
    if (!categoryTotal || categories.size !== categoryTotal || expanded.size !== categoryTotal) {
      return { status: "contract", reason: `дерево раскрыто частично: ${expanded.size}/${categoryTotal}`, url: location.href };
    }
    scroller.scrollTop = 0; await pause(100);
    let position = 0;
    for (let step = 0; step < 4000; step++) {
      inspect(false);
      const next = Math.min(scroller.scrollHeight - scroller.clientHeight, position + Math.max(80, scroller.clientHeight / 2));
      if (next <= position + 1) break;
      scroller.scrollTop = next; position = next; await pause(35);
    }
    inspect(false);
    for (const category of categories) {
      const expected = expectedChildren.get(category);
      const observed = observedChildren.get(category)?.size || 0;
      if ((expected === undefined && categoryCounts.get(category) !== 0) ||
          (expected !== undefined && observed !== expected)) {
        return { status: "contract", reason: `пункты группы ${category} просмотрены частично: ${observed}/${expected ?? "?"}`, url: location.href };
      }
    }
    return { status: "ok", url: location.href, total, roles: [...roles.values()], tree_complete: true };
  } catch (error) {
    return { status: "contract", reason: String(error), url: location.href };
  }
}

document.getElementById("start").addEventListener("click", async () => {
  if (running || !tokenInput.value || !/^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(serverInput.value)) {
    status("Укажите локальный адрес и токен."); return;
  }
  running = true;
  document.getElementById("start").disabled = true;
  document.getElementById("stop").disabled = false;
  while (running) {
    try {
      const { command } = await api("next");
      if (!running) break;
      if (!command) { status("Подключено. Ожидаю задачу."); continue; }
      let result;
      try { result = await search(command); }
      catch (error) { result = { status: "unavailable", reason: String(error) }; }
      const answer = await api("result", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command_id: command.id, result }),
      });
      status(answer.accepted ? `Поиск завершён: ${command.target}; результат: ${result.status}` : "Ответ опоздал; сервер повторит запрос.");
    } catch (error) { status(`${error}. Повтор подключения через 10 секунд.`); await wait(10000); }
  }
  document.getElementById("start").disabled = false;
  document.getElementById("stop").disabled = true;
});
document.getElementById("stop").addEventListener("click", () => { running = false; status("Остановлено."); });
