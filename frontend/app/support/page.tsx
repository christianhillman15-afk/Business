"use client";

import { useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { useAuth } from "@/lib/useAuth";
import { api } from "@/lib/api";

interface ChatMsg {
  role: "user" | "assistant";
  content: string;
}

const GREETING =
  "Hi! I'm your LeadPilot assistant 👋 Ask me anything — how leads work, " +
  "getting them by text, pricing, or connecting your accounts.";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// How long the "typing…" bubble lingers before a reply lands — longer for
// longer messages, so the bot feels like it's actually composing a text.
// ~18ms/char, between 0.8s and 3.5s.
function typingDelay(text: string) {
  return Math.min(3500, Math.max(800, Math.round(text.length * 18)));
}

// Keep the typing bubble up for the composed duration, minus whatever the API
// already took (so a slow real backend doesn't get double-delayed).
async function typingPause(text: string, startedAt: number) {
  const wait = typingDelay(text) - (Date.now() - startedAt);
  if (wait > 0) await sleep(wait);
}

export default function SupportPage() {
  const { user, loading, logout } = useAuth();
  const [messages, setMessages] = useState<ChatMsg[]>([
    { role: "assistant", content: GREETING },
  ]);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [ticketId, setTicketId] = useState<number | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  useEffect(() => {
    if (!user) return;
    api
      .get<{ suggestions: string[] }>("/api/support/suggestions")
      .then((r) => setSuggestions(r.suggestions))
      .catch(() => {});
  }, [user]);

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-400">
        Loading…
      </div>
    );
  }

  async function sendText(raw: string) {
    const text = raw.trim();
    if (!text || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: text }]);
    setBusy(true);
    const started = Date.now();
    try {
      const res = await api.post<{
        ticket_id: number;
        reply: string;
        escalated: boolean;
      }>("/api/support/chat", { ticket_id: ticketId, message: text });
      setTicketId(res.ticket_id);
      // Linger on the typing bubble for a natural, length-based beat.
      await typingPause(res.reply, started);
      setMessages((m) => [...m, { role: "assistant", content: res.reply }]);
      if (res.escalated) {
        // A second "text" — show the typing bubble again briefly.
        const note =
          "⤴ I've looped in a human teammate — they'll follow up by email shortly.";
        await typingPause(note, Date.now());
        setMessages((m) => [...m, { role: "assistant", content: note }]);
      }
    } catch {
      await sleep(700);
      setMessages((m) => [
        ...m,
        { role: "assistant", content: "Sorry, something went wrong. Try again." },
      ]);
    } finally {
      setBusy(false);
    }
  }

  const showSuggestions = suggestions.length > 0 && messages.length <= 3;

  return (
    <AppShell user={user} onLogout={logout}>
      <h1 className="mb-1 text-2xl font-bold">Support</h1>
      <p className="mb-5 text-sm text-slate-500">
        Your AI assistant — instant answers, with a human on standby for billing
        and account issues.
      </p>

      {/* SMS framing */}
      <div className="mb-5 flex flex-wrap items-center gap-3 rounded-2xl border border-indigo-100 bg-gradient-to-r from-indigo-50 to-fuchsia-50 px-4 py-3">
        <span className="text-xl">📱</span>
        <p className="text-sm text-slate-700">
          <span className="font-semibold">Prefer texting?</span> Your bot answers
          by SMS too — text your LeadPilot number any question and get leads and
          replies straight to your phone.
        </p>
      </div>

      <div className="card overflow-hidden p-0">
        {/* Assistant header */}
        <div className="flex items-center gap-3 border-b border-slate-100 bg-white px-4 py-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-fuchsia-500 text-lg text-white shadow-sm">
            ✨
          </div>
          <div>
            <div className="text-sm font-semibold text-slate-800">
              LeadPilot Assistant
            </div>
            <div className="lp-live text-xs text-green-600">
              <span className="lp-live-core" aria-hidden />
              Online · replies instantly
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex h-[52vh] flex-col">
          <div className="flex-1 space-y-3 overflow-y-auto bg-slate-50/60 px-4 py-4">
            {messages.map((m, i) => (
              <div
                key={i}
                className={`flex ${
                  m.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                <div
                  className={`max-w-[82%] rounded-2xl px-4 py-2.5 text-sm shadow-sm ${
                    m.role === "user"
                      ? "rounded-br-md bg-brand-600 text-white"
                      : "rounded-bl-md border border-slate-200 bg-white text-slate-800"
                  }`}
                >
                  {m.content}
                </div>
              </div>
            ))}
            {busy && (
              <div className="flex justify-start">
                <div className="flex items-center gap-1 rounded-2xl rounded-bl-md border border-slate-200 bg-white px-4 py-3">
                  <Dot delay="0ms" />
                  <Dot delay="150ms" />
                  <Dot delay="300ms" />
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>

          {/* Suggested questions */}
          {showSuggestions && (
            <div className="border-t border-slate-100 bg-white px-3 pt-3">
              <div className="mb-2 px-1 text-xs font-medium uppercase tracking-wide text-slate-400">
                Try asking
              </div>
              <div className="flex flex-wrap gap-2 pb-1">
                {suggestions.map((q) => (
                  <button
                    key={q}
                    onClick={() => sendText(q)}
                    disabled={busy}
                    className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Input */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              sendText(input);
            }}
            className="flex gap-2 border-t border-slate-100 bg-white p-3"
          >
            <input
              className="input"
              placeholder="Type your question…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
            />
            <button className="btn-primary" disabled={busy || !input.trim()}>
              {busy ? "…" : "Send"}
            </button>
          </form>
        </div>
      </div>
    </AppShell>
  );
}

function Dot({ delay }: { delay: string }) {
  return (
    <span
      className="inline-block h-2 w-2 animate-bounce rounded-full bg-slate-300"
      style={{ animationDelay: delay }}
    />
  );
}
