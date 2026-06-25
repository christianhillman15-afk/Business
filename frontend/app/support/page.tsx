"use client";

import { useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { useAuth } from "@/lib/useAuth";
import { api } from "@/lib/api";

interface ChatMsg {
  role: "user" | "assistant";
  content: string;
}

export default function SupportPage() {
  const { user, loading, logout } = useAuth();
  const [messages, setMessages] = useState<ChatMsg[]>([
    {
      role: "assistant",
      content:
        "Hi! I'm the LeadPilot assistant. Ask me about connecting accounts, " +
        "pricing, your daily quota, or billing.",
    },
  ]);
  const [ticketId, setTicketId] = useState<number | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-400">
        Loading…
      </div>
    );
  }

  async function send(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: text }]);
    setBusy(true);
    try {
      const res = await api.post<{
        ticket_id: number;
        reply: string;
        escalated: boolean;
      }>("/api/support/chat", { ticket_id: ticketId, message: text });
      setTicketId(res.ticket_id);
      setMessages((m) => [
        ...m,
        { role: "assistant", content: res.reply },
        ...(res.escalated
          ? [
              {
                role: "assistant" as const,
                content: "⤴ This has been escalated to a human on our team.",
              },
            ]
          : []),
      ]);
    } catch {
      setMessages((m) => [
        ...m,
        { role: "assistant", content: "Sorry, something went wrong. Try again." },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell user={user} onLogout={logout}>
      <h1 className="mb-1 text-2xl font-bold">Support</h1>
      <p className="mb-6 text-sm text-slate-500">
        AI assistant with human escalation for billing and account issues.
      </p>

      <div className="card flex h-[60vh] flex-col">
        <div className="flex-1 space-y-3 overflow-y-auto pr-1">
          {messages.map((m, i) => (
            <div
              key={i}
              className={`flex ${
                m.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm ${
                  m.role === "user"
                    ? "bg-brand-600 text-white"
                    : "bg-slate-100 text-slate-800"
                }`}
              >
                {m.content}
              </div>
            </div>
          ))}
          <div ref={endRef} />
        </div>
        <form onSubmit={send} className="mt-3 flex gap-2 border-t border-slate-100 pt-3">
          <input
            className="input"
            placeholder="Type your question…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
          <button className="btn-primary" disabled={busy}>
            {busy ? "…" : "Send"}
          </button>
        </form>
      </div>
    </AppShell>
  );
}
