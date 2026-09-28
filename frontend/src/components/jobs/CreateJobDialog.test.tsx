import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { CreateJobDialog } from "./CreateJobDialog";

test("counts vacancy and resume URLs for every selected profession", async () => {
  HTMLDialogElement.prototype.showModal ??= function showModal() { this.open = true; };
  HTMLDialogElement.prototype.close ??= function close() { this.open = false; };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(["roles"], [
    { id: "96", name: "Разработчик" },
    { id: "160", name: "DevOps" },
  ]);
  render(
    <QueryClientProvider client={client}>
      <CreateJobDialog open onClose={() => undefined} />
    </QueryClientProvider>,
  );

  expect(await screen.findByText(/вакансии 2, резюме 2, всего 4/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("switch", { name: /Собирать страты опыта/ }));
  expect(screen.getByText(/вакансии 10, резюме 10, всего 20/)).toBeInTheDocument();
});
