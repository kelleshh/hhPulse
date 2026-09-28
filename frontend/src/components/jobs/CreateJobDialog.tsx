import { useState, type FormEvent } from "react";
import { useCreateJob, useRoles } from "../../data/queries";
import type { CreateJobInput } from "../../domain/types";
import { Button } from "../ui/Button";
import { Dialog } from "../ui/Dialog";
import { Toggle } from "../ui/Toggle";

interface CreateJobDialogProps {
  open: boolean;
  onClose: () => void;
}

const initialForm: CreateJobInput = {
  name: "",
  regionIds: ["1"],
  roleSelectionMode: "all",
  roleIds: [],
  includeExperienceStrata: false,
  vacancySlices: [],
  resumeSlices: [],
  maxConcurrency: 1,
  maxRps: 0.25,
  userAgentMode: "shared",
  timezone: "Europe/Moscow",
  enabled: true,
};

export function CreateJobDialog({ open, onClose }: CreateJobDialogProps) {
  const [form, setForm] = useState(initialForm);
  const [roleSearch, setRoleSearch] = useState("");
  const roles = useRoles();
  const createJob = useCreateJob();
  const visibleRoles = roles.data?.filter((role) => role.name.toLocaleLowerCase("ru").includes(roleSearch.toLocaleLowerCase("ru"))) ?? [];
  const roleCount = form.roleSelectionMode === "all" ? roles.data?.length : form.roleIds.length;
  const strata = form.includeExperienceStrata ? 5 : 1;
  const cost = (names: string[], target: "vacancy" | "resume", remote: boolean) => {
    const options: Record<string, number> = target === "vacancy"
      ? { low_responses: 1, salary_present: 1, work_format: remote ? 0 : 5, employment: 4, education: 3 }
      : { salary_present: 1, work_format: remote ? 0 : 5, employment: 5, education: 8 };
    return 1 + names.reduce((sum, name) => sum + (options[name] ?? 0), 0);
  };
  const vacancyLoads = roleCount == null ? null : form.regionIds.reduce((sum, region) => sum + strata * roleCount * cost(form.vacancySlices, "vacancy", region === "remote"), 0);
  const resumeLoads = roleCount == null ? null : form.regionIds.reduce((sum, region) => sum + strata * roleCount * cost(form.resumeSlices, "resume", region === "remote"), 0);
  const loads = vacancyLoads == null || resumeLoads == null ? null : vacancyLoads + resumeLoads;
  const toggleSlice = (target: "vacancySlices" | "resumeSlices", name: string) => setForm((current) => ({
    ...current,
    [target]: current[target].includes(name)
      ? current[target].filter((item) => item !== name) : [...current[target], name],
  }));

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    await createJob.mutateAsync(form);
    setForm(initialForm);
    onClose();
  };

  const toggleRole = (roleId: string) => {
    setForm((current) => ({
      ...current,
      roleIds: current.roleIds.includes(roleId)
        ? current.roleIds.filter((id) => id !== roleId)
        : [...current.roleIds, roleId],
    }));
  };

  return (
    <Dialog open={open} title="Новая задача сбора" description="Один полный дневной срез публикуется только после завершения всех запросов." onClose={onClose}>
      <form className="job-form" onSubmit={submit}>
        <section>
          <h3>Что наблюдаем</h3>
          <label className="field"><span>Название задачи</span><input required minLength={2} maxLength={120} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Например, Весь рынок Москвы" /></label>
          <label className="field"><span>Регион</span><select value={form.regionIds[0]} onChange={(event) => setForm({ ...form, regionIds: [event.target.value] })}><option value="1">Москва</option><option value="2">Санкт-Петербург</option><option value="113">Россия</option><option value="remote">Удалёнка · вся Россия</option></select></label>
          <div className="field">
            <span>Профессии</span>
            <div className="radio-stack">
              <label><input type="radio" name="roles" checked={form.roleSelectionMode === "all"} onChange={() => setForm({ ...form, roleSelectionMode: "all" })} />Все профессии из справочника HH</label>
              <label><input type="radio" name="roles" checked={form.roleSelectionMode === "selected"} onChange={() => setForm({ ...form, roleSelectionMode: "selected" })} />Только выбранные</label>
            </div>
          </div>
          {form.roleSelectionMode === "selected" ? (
            <div className="role-picker">
              <input value={roleSearch} onChange={(event) => setRoleSearch(event.target.value)} placeholder="Поиск профессии" aria-label="Поиск профессии" />
              <div className="role-picker__list">
                {visibleRoles.map((role) => <label key={role.id}><input type="checkbox" checked={form.roleIds.includes(role.id)} onChange={() => toggleRole(role.id)} />{role.name}</label>)}
              </div>
              <small>Выбрано: {form.roleIds.length}</small>
            </div>
          ) : null}
          {roles.error ? <p className="form-error" role="alert">Не удалось загрузить справочник профессий: {roles.error.message}</p> : null}
          <Toggle checked={form.includeExperienceStrata} onChange={(checked) => setForm({ ...form, includeExperienceStrata: checked })} label="Собирать страты опыта" description="Отдельные запросы: без опыта, 1–3, 3–6 и более 6 лет" />
          <h3>Дополнительные поисковые срезы вакансий</h3>
          {([ ["low_responses", "Меньше 10 откликов"], ["salary_present", "Зарплата указана"], ["work_format", "Формат работы"], ["employment", "Занятость"], ["education", "Образование"] ] as const).map(([key, label]) => <Toggle key={key} checked={form.vacancySlices.includes(key)} onChange={() => toggleSlice("vacancySlices", key)} label={label} />)}
          <h3>Дополнительные поисковые срезы резюме</h3>
          {([ ["salary_present", "Желаемая зарплата указана"], ["work_format", "Формат работы"], ["employment", "Занятость"], ["education", "Образование"] ] as const).map(([key, label]) => <Toggle key={key} checked={form.resumeSlices.includes(key)} onChange={() => toggleSlice("resumeSlices", key)} label={label} />)}
        </section>

        <section>
          <h3>Нагрузка на HH</h3>
          <p className="form-note">Поисковых загрузок: вакансии {vacancyLoads ?? "ожидаем справочник профессий"}, резюме {resumeLoads ?? "ожидаем справочник профессий"}, всего {loads ?? "—"}.</p>
          <p className="form-note">Оценка времени: {loads == null ? "—" : `${Math.ceil(loads * 3 / 60)}–${Math.ceil(loads * 12 / 60)} мин`}. Реальная скорость зависит от загрузки HH. Это число страниц поиска, а не всех HTTP-запросов Chrome.</p>
          <input type="hidden" value={form.userAgentMode} />
          <p className="form-note">Нужна открытая вкладка расширения hhPulse в авторизованном Chrome. Один поиск за раз, пауза 2–4 секунды. При ограничении доступа сбор останавливается.</p>
        </section>

        {createJob.error ? <p className="form-error" role="alert">{createJob.error.message}</p> : null}
        <div className="dialog__actions">
          <Button type="button" variant="quiet" onClick={onClose}>Отменить</Button>
          <Button type="submit" variant="primary" disabled={createJob.isPending || roleCount == null || roleCount === 0}>{createJob.isPending ? "Создаю…" : "Создать задачу"}</Button>
        </div>
      </form>
    </Dialog>
  );
}
