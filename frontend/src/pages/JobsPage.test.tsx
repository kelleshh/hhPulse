import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { JobsPage } from "./JobsPage";

describe("JobsPage", () => {
  it("shows persisted collection configuration", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter><JobsPage /></MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findByText("Весь рынок Москвы")).toBeInTheDocument();
    expect(screen.getByText("0.8 запр./с")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Новая задача/ })).toBeEnabled();
  });
});
