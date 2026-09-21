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
  maxConcurrency: 1,
  maxRps: 1,
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
          <label className="field"><span>Регион</span><select value={form.regionIds[0]} onChange={(event) => setForm({ ...form, regionIds: [event.target.value] })}><option value="1">Москва</option><option value="2">Санкт-Петербург</option><option value="113">Россия</option></select></label>
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
          <Toggle checked={form.includeExperienceStrata} onChange={(checked) => setForm({ ...form, includeExperienceStrata: checked })} label="Собирать страты опыта" description="Отдельные запросы: без опыта, 1–3, 3–6 и более 6 лет" />
        </section>

        <section>
          <h3>Нагрузка на HH</h3>
          <div className="form-grid">
            <label className="field"><span>Одновременные запросы</span><input type="number" value={1} disabled /></label>
            <label className="field"><span>Максимум запросов/с</span><input type="number" min={0.1} max={1} step={0.1} value={form.maxRps} onChange={(event) => setForm({ ...form, maxRps: event.target.valueAsNumber })} /></label>
          </div>
          <input type="hidden" value={form.userAgentMode} />
          <p className="form-note">Один requests.Session и постоянный User-Agent. После каждого ответа — случайная пауза 0,9–1,8 с. Сначала собираются все резюме, затем все вакансии. При WAF/403 запуск немедленно остановится.</p>
        </section>

        {createJob.error ? <p className="form-error" role="alert">{createJob.error.message}</p> : null}
        <div className="dialog__actions">
          <Button type="button" variant="quiet" onClick={onClose}>Отменить</Button>
          <Button type="submit" variant="primary" disabled={createJob.isPending || (form.roleSelectionMode === "selected" && form.roleIds.length === 0)}>{createJob.isPending ? "Создаю…" : "Создать задачу"}</Button>
        </div>
      </form>
    </Dialog>
  );
}
