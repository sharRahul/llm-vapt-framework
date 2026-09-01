import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiGet, clearCsrfToken } from "@/lib/api";

function respond(status: number, body: string) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 502 ? "Bad Gateway" : "Error",
    text: async () => body,
    json: async () => JSON.parse(body),
  } as Response;
}

afterEach(() => {
  clearCsrfToken();
});

describe("API error messages", () => {
  it("shows the server's message, not the JSON envelope around it", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => respond(502, JSON.stringify({ error: "docker build failed:\nstep 3" }))));
    await expect(apiGet("/api/agents")).rejects.toMatchObject({
      status: 502,
      message: "docker build failed:\nstep 3",
    });
  });

  it("falls back to the raw body when it is not a JSON envelope", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => respond(404, "Not found")));
    await expect(apiGet("/api/nope")).rejects.toMatchObject({ status: 404, message: "Not found" });
  });

  it("falls back to the status text when there is no body at all", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => respond(502, "")));
    await expect(apiGet("/api/nope")).rejects.toMatchObject({ message: "Bad Gateway" });
  });

  it("survives a body that only looks like JSON", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => respond(500, "{not json")));
    await expect(apiGet("/api/nope")).rejects.toMatchObject({ message: "{not json" });
  });

  it("returns the parsed body on success", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => respond(200, JSON.stringify({ ok: true }))));
    await expect(apiGet<{ ok: boolean }>("/api/ok")).resolves.toEqual({ ok: true });
  });

  it("carries the status on the thrown error", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => respond(403, JSON.stringify({ error: "forbidden" }))));
    const error = await apiGet("/api/x").catch((exc) => exc);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(403);
  });
});
