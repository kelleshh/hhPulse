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

// This function runs inside hh.ru and returns aggregate counts only.
async function extractSearch(target) {
  const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const selector = target === "resume" ? '[data-qa="search-title"]' : 'h1[data-qa="title"]';
  for (let attempt = 0; attempt < 100 && !document.querySelector(selector); attempt++) {
    if (/captcha|капча|access denied|too many requests/i.test(document.title)) break;
    await pause(150);
  }
  await pause(500);
  const text = document.body.innerText;
  const title = document.title.toLowerCase();
  const url = location.href;
  if (/captcha|капча|access denied|too many requests|слишком много запросов/i.test(title) ||
      /^(доступ ограничен|проверка безопасности|too many requests)/i.test(text.trim().slice(0, 200))) {
    return { status: "blocked", reason: "страница защиты или ограничения", url };
  }
  if (/войти|авторизац/i.test(title) && !document.querySelector(selector)) {
    return { status: "auth", reason: "нужно войти в аккаунт работодателя", url };
  }
  const heading = document.querySelector(selector)?.innerText || "";
  const number = (raw) => {
    const digits = (raw || "").replace(/[^\d]/g, "");
    const value = Number(digits);
    return digits && Number.isSafeInteger(value) ? value : null;
  };
  if (target === "vacancy") {
    const total = number(heading.match(/[\d\s\u00a0\u202f]+(?=\s*ваканси)/i)?.[0]) ??
      (/ничего не найдено|вакансии не найдены/i.test(heading) ? 0 : null);
    return total === null
      ? { status: "contract", reason: "счётчик вакансий не найден", url }
      : { status: "ok", url, total };
  }
  const visible = number(heading.match(/[\d\s\u00a0\u202f]+(?=\s*резюм)/i)?.[0]) ??
    (/ничего не найдено|резюме не найден/i.test(heading) ? 0 : null);
  const hiddenMatches = [...text.matchAll(/([\d\s\u00a0\u202f]+)\s+резюме\s+скрыт/gi)];
  const hiddenCounts = new Set(hiddenMatches.map((match) => number(match[1])));
  if (visible === null || hiddenCounts.size > 1 || hiddenCounts.has(null) ||
      (!hiddenMatches.length && /резюме\s+скрыт/i.test(text))) {
    return { status: "contract", reason: "счётчики резюме неоднозначны", url };
  }
  const hidden = hiddenMatches.length ? hiddenCounts.values().next().value : 0;
  const total = visible + hidden;
  if (!Number.isSafeInteger(total)) {
    return { status: "contract", reason: "счётчик резюме слишком велик", url };
  }
  return { status: "ok", url, total, visible, hidden };
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
