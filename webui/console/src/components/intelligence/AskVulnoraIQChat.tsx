import { useEffect, useRef, useState } from "react";
import { Bot, Loader2, SendHorizonal, Settings2, ShieldQuestion } from "lucide-react";
import type { ChatMessage as ChatMessageType, Finding } from "@/types";
import { Button } from "@/components/ui/button";
import { ChatMessage } from "./ChatMessage";
import { apiGet, apiPost } from "@/lib/api";

const starterPrompts: string[] = [
  "Explain this finding in plain language.",
  "What evidence should I review before closing this finding?",
  "Suggest safe validation steps for this authorised assessment.",
];

let idCounter = 0;
const nextId = () => `m-${++idCounter}`;

interface AssistantControls {
  provider: string;
  model: string;
  temperature: number;
  system_prompt: string;
  max_tokens: number;
}

interface AssistantConfig {
  provider: string;
  default_model: string;
  allowed_models: string[];
  default_temperature: number;
  default_system_prompt: string;
}

export function AskVulnoraIQChat({ finding }: { finding: Finding }) {
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [showControls, setShowControls] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [controls, setControls] = useState<AssistantControls>({
    provider: "local",
    model: "nora-assistant",
    temperature: 0.2,
    system_prompt: "Provide concise guidance for authorised internal assessment work.",
    max_tokens: 800,
  });
  const [allowedModels, setAllowedModels] = useState<string[]>(["nora-assistant"]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void apiGet<AssistantConfig>("/api/assistant/config")
      .then((config) => {
        setAllowedModels(config.allowed_models?.length ? config.allowed_models : [config.default_model]);
        setControls({
          provider: config.provider || "local",
          model: config.default_model || "nora-assistant",
          temperature: config.default_temperature ?? 0.2,
          system_prompt: config.default_system_prompt,
          max_tokens: 800,
        });
      })
      .catch((exc) => setError(exc instanceof Error ? exc.message : String(exc)));
  }, []);

  useEffect(() => {
    setMessages([
      {
        id: nextId(),
        role: "assistant",
        content: `I can help you understand and validate "${finding.title}" using the configured backend service.`,
      },
    ]);
  }, [finding.id, finding.title]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    const userMsg: ChatMessageType = { id: nextId(), role: "user", content: trimmed };
    const pending: ChatMessageType = { id: nextId(), role: "assistant", content: "", pending: true };
    const nextMessages = [...messages, userMsg];
    setMessages((prev) => [...prev, userMsg, pending]);
    setInput("");
    setBusy(true);
    setError(null);

    try {
      const response = await apiPost<{ content: string; model: string; provider: string; latency_ms?: number }>("/api/assistant/chat", {
            message: trimmed,
            messages: nextMessages.map(({ role, content }) => ({ role, content })),
            finding,
            controls,
          });
      setMessages((prev) =>
        prev.map((m) =>
          m.id === pending.id
            ? {
                ...m,
                pending: false,
                content: `${response.content}\n\n_Provider: ${response.provider}; model: ${response.model}; latency: ${response.latency_ms ?? 0}ms_`,
              }
            : m,
        ),
      );
    } catch (exc) {
      const message = exc instanceof Error ? exc.message : String(exc);
      setError(message);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === pending.id ? { ...m, pending: false, content: `Assistant backend error: ${message}` } : m,
        ),
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border p-3">
        <button
          type="button"
          onClick={() => setShowControls((value) => !value)}
          className="flex w-full items-center justify-between rounded-md border border-border bg-card px-2.5 py-2 text-left text-xs font-semibold text-foreground hover:bg-muted"
        >
          <span className="flex items-center gap-1.5"><Settings2 className="size-3.5" /> Model controls</span>
          <span className="text-muted-foreground">{controls.model} · {controls.temperature.toFixed(1)}</span>
        </button>
        {showControls ? (
          <div className="mt-3 space-y-2 rounded-md border border-border bg-muted p-3 text-xs">
            <label className="block font-semibold">Model
              <select value={controls.model} onChange={(e) => setControls({ ...controls, model: e.target.value })} className="input mt-1 text-xs">
                {allowedModels.map((model) => <option key={model}>{model}</option>)}
              </select>
            </label>
            <label className="block font-semibold">Temperature: {controls.temperature.toFixed(1)}
              <input type="range" min="0" max="1" step="0.1" value={controls.temperature} onChange={(e) => setControls({ ...controls, temperature: Number(e.target.value) })} className="mt-1 w-full" />
            </label>
            <label className="block font-semibold">Instruction text
              <textarea value={controls.system_prompt} onChange={(e) => setControls({ ...controls, system_prompt: e.target.value })} className="input mt-1 min-h-24 text-xs" />
            </label>
          </div>
        ) : null}
        {error ? <p className="mt-2 text-xs text-severity-high">{error}</p> : null}
      </div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto scrollbar-thin p-3">
        {messages.map((m) => <ChatMessage key={m.id} message={m} />)}
        {messages.length <= 1 && (
          <div className="pt-1">
            <p className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              <ShieldQuestion className="size-3.5" /> Try asking
            </p>
            <div className="flex flex-col gap-1.5">
              {starterPrompts.map((prompt) => (
                <button key={prompt} onClick={() => void send(prompt)} className="rounded-md border border-border bg-card px-2.5 py-1.5 text-left text-xs font-medium text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <form onSubmit={(e) => { e.preventDefault(); void send(input); }} className="border-t border-border p-3">
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(input); } }}
            rows={1}
            placeholder="Ask VulnoraIQ about this finding…"
            aria-label="Ask VulnoraIQ"
            className="max-h-28 min-h-[38px] flex-1 resize-none rounded-md border border-border bg-canvas px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          <Button type="submit" variant="primary" size="icon" disabled={busy || !input.trim()} aria-label="Send message">
            {busy ? <Loader2 className="size-4 animate-spin" /> : <SendHorizonal className="size-4" />}
          </Button>
        </div>
        <p className="mt-2 flex items-center gap-1.5 text-[10.5px] leading-snug text-muted-foreground">
          <Bot className="size-3 shrink-0" /> Assistant recommendations are advisory and require human review.
        </p>
      </form>
    </div>
  );
}
