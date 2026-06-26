"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { useAuth } from "@/lib/useAuth";
import { ApiError, api, Capabilities, Lead, Quota, User } from "@/lib/api";

function scoreBadge(score: number | null) {
  if (score === null) return null;
  const pct = Math.round(score * 100);
  const cls =
    score >= 0.7
      ? "bg-green-100 text-green-700"
      : score >= 0.5
      ? "bg-amber-100 text-amber-700"
      : "bg-slate-100 text-slate-500";
  return <span className={`badge ${cls}`}>{pct}% match</span>;
}

export default function DashboardPage() {
  const { user, loading, logout, setUser } = useAuth();
  const [leads, setLeads] = useState<Lead[]>([]);
  const [quota, setQuota] = useState<Quota | null>(null);
  const [caps, setCaps] = useState<Capabilities>({});
  const [discovering, setDiscovering] = useState(false);
  const [trialEnded, setTrialEnded] = useState(false);

  const refresh = useCallback(async () => {
    const [l, q, c] = await Promise.all([
      api.get<Lead[]>("/api/leads"),
      api.get<Quota>("/api/leads/quota"),
      api.get<Capabilities>("/api/capabilities"),
    ]);
    setLeads(l);
    setQuota(q);
    setCaps(c);
  }, []);

  useEffect(() => {
    if (user) refresh().catch(() => {});
  }, [user, refresh]);

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-400">
        Loading…
      </div>
    );
  }

  const matched = leads.filter((l) =>
    ["matched", "drafted", "engaged"].includes(l.status),
  );
  const other = leads.filter(
    (l) => !["matched", "drafted", "engaged"].includes(l.status),
  );

  async function discover() {
    setDiscovering(true);
    try {
      await api.post("/api/leads/discover");
      setTrialEnded(false);
      await refresh();
    } catch (err) {
      if (err instanceof ApiError && err.status === 402) setTrialEnded(true);
    } finally {
      setDiscovering(false);
    }
  }

  async function toggleAutomation() {
    const r = await api.post<{ automation_enabled: boolean }>(
      "/api/automation/toggle",
    );
    setUser({ ...(user as User), automation_enabled: r.automation_enabled });
  }

  return (
    <AppShell user={user} onLogout={logout}>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">Dashboard</h1>
            <span className="lp-live text-xs font-semibold uppercase tracking-wide text-green-600">
              <span className="lp-live-core" aria-hidden />
              Live
            </span>
          </div>
          <p className="text-sm text-slate-500">
            AI watches your local feeds and drafts replies for leads in your
            trade. You approve before anything posts.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="btn-ghost"
            onClick={toggleAutomation}
            title="Master switch for AI posting"
          >
            Automation: {user.automation_enabled ? "ON" : "OFF"}
          </button>
          <button className="btn-primary" onClick={discover} disabled={discovering}>
            {discovering ? "Scanning…" : "Scan for leads"}
          </button>
        </div>
      </div>

      {trialEnded && (
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
          <span className="text-sm text-amber-800">
            Your free trial has ended. Choose a plan to keep finding and posting
            leads.
          </span>
          <Link href="/billing" className="btn-primary">
            Choose a plan
          </Link>
        </div>
      )}

      <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat
          label="Plan"
          value={quota ? (quota.on_trial ? "Free trial" : quota.plan_code) : "—"}
        />
        <Stat
          label="Daily quota"
          value={quota ? `${quota.daily_quota}` : "—"}
        />
        <Stat
          label="Posted today"
          value={quota ? `${quota.used_today}` : "—"}
        />
        <Stat
          label="Remaining"
          value={quota ? `${quota.remaining_today}` : "—"}
          highlight={quota?.remaining_today === 0}
        />
      </div>

      <section className="mb-10">
        <h2 className="mb-3 text-lg font-semibold">
          In-field leads{" "}
          <span className="text-sm font-normal text-slate-400">
            ({matched.length})
          </span>
        </h2>
        {matched.length === 0 ? (
          <div className="card text-sm text-slate-500">
            No matched leads yet. Click <strong>Scan for leads</strong> to find
            posts in your trade.
          </div>
        ) : (
          <div className="space-y-3">
            {matched.map((lead) => (
              <LeadCard
                key={lead.id}
                lead={lead}
                canAutopost={caps[lead.provider]?.reply_autopost ?? true}
                onChange={refresh}
              />
            ))}
          </div>
        )}
      </section>

      {other.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-semibold text-slate-500">
            Filtered out{" "}
            <span className="text-sm font-normal text-slate-400">
              ({other.length}) — not in your trade
            </span>
          </h2>
          <div className="space-y-2">
            {other.slice(0, 8).map((lead) => (
              <div
                key={lead.id}
                className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="truncate">{lead.content}</span>
                  {scoreBadge(lead.relevance_score)}
                </div>
                {lead.relevance_reason && (
                  <p className="mt-1 text-xs text-slate-400">
                    {lead.relevance_reason}
                  </p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
    </AppShell>
  );
}

function Stat({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div className="card">
      <div className="text-xs uppercase tracking-wide text-slate-400">
        {label}
      </div>
      <div
        className={`lp-stat mt-1 text-2xl font-bold ${
          highlight ? "text-red-600" : "text-slate-800"
        }`}
      >
        {value}
      </div>
    </div>
  );
}

function LeadCard({
  lead,
  canAutopost,
  onChange,
}: {
  lead: Lead;
  canAutopost: boolean;
  onChange: () => void;
}) {
  const [text, setText] = useState(lead.response?.generated_text ?? "");
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const posted = lead.response?.status === "posted";

  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await onChange();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
        <span className="badge bg-brand-50 capitalize text-brand-700">
          {lead.provider}
        </span>
        {scoreBadge(lead.relevance_score)}
        {lead.location && <span>· {lead.location}</span>}
        {lead.author && <span>· {lead.author}</span>}
        {posted && (
          <span className="badge bg-green-100 text-green-700">Posted</span>
        )}
      </div>

      <p className="text-sm text-slate-800">{lead.content}</p>
      {lead.relevance_reason && (
        <p className="mt-1 text-xs text-slate-400">
          Why it matched: {lead.relevance_reason}
        </p>
      )}

      {lead.response && (
        <div className="mt-3 rounded-lg bg-slate-50 p-3">
          <div className="mb-1 text-xs font-medium text-slate-500">
            AI draft reply
          </div>
          {editing ? (
            <textarea
              className="input min-h-[90px]"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          ) : (
            <p className="text-sm text-slate-700">
              {lead.response.generated_text}
            </p>
          )}

          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

          {!posted && (
            <div className="mt-3 flex flex-wrap gap-2">
              {editing ? (
                <>
                  <button
                    className="btn-primary"
                    disabled={busy}
                    onClick={() =>
                      act(async () => {
                        await api.put(
                          `/api/responses/${lead.response!.id}`,
                          { generated_text: text },
                        );
                        setEditing(false);
                      })
                    }
                  >
                    Save
                  </button>
                  <button
                    className="btn-ghost"
                    onClick={() => {
                      setText(lead.response!.generated_text);
                      setEditing(false);
                    }}
                  >
                    Cancel
                  </button>
                </>
              ) : canAutopost ? (
                <>
                  <button
                    className="btn-primary"
                    disabled={busy}
                    onClick={() =>
                      act(() =>
                        api.post(
                          `/api/responses/${lead.response!.id}/approve`,
                        ),
                      )
                    }
                  >
                    Approve &amp; post
                  </button>
                  <button
                    className="btn-ghost"
                    onClick={() => setEditing(true)}
                  >
                    Edit
                  </button>
                  <button
                    className="btn-ghost"
                    disabled={busy}
                    onClick={() =>
                      act(() =>
                        api.post(
                          `/api/responses/${lead.response!.id}/reject`,
                        ),
                      )
                    }
                  >
                    Reject
                  </button>
                </>
              ) : (
                // Assist flow: platform has no reply API (e.g. Nextdoor), so the
                // client posts the reply themselves, then confirms it here.
                <>
                  <button
                    className="btn-primary"
                    onClick={async () => {
                      await navigator.clipboard?.writeText(
                        lead.response!.generated_text,
                      );
                      setCopied(true);
                      setTimeout(() => setCopied(false), 1500);
                    }}
                  >
                    {copied ? "Copied ✓" : "Copy reply"}
                  </button>
                  {lead.post_url && (
                    <a
                      className="btn-ghost"
                      href={lead.post_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Open post ↗
                    </a>
                  )}
                  <button
                    className="btn-ghost"
                    disabled={busy}
                    onClick={() =>
                      act(() =>
                        api.post(
                          `/api/responses/${lead.response!.id}/mark-posted`,
                        ),
                      )
                    }
                  >
                    I posted it
                  </button>
                  <button
                    className="btn-ghost"
                    onClick={() => setEditing(true)}
                  >
                    Edit
                  </button>
                  <button
                    className="btn-ghost text-slate-500"
                    disabled={busy}
                    onClick={() =>
                      act(() =>
                        api.post(`/api/responses/${lead.response!.id}/reject`),
                      )
                    }
                  >
                    Don&apos;t post
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
