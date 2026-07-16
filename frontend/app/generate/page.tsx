"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { useAuth } from "@/lib/useAuth";
import {
  ApiError,
  api,
  GenerateResult,
  GenerationItem,
  GenerationUsage,
} from "@/lib/api";

export default function GeneratePage() {
  const { user, loading, logout } = useAuth();
  const [post, setPost] = useState("");
  const [platform, setPlatform] = useState("nextdoor");
  const [usage, setUsage] = useState<GenerationUsage | null>(null);
  const [reply, setReply] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [limitReached, setLimitReached] = useState(false);
  const [copied, setCopied] = useState(false);
  const [history, setHistory] = useState<GenerationItem[]>([]);

  const load = useCallback(async () => {
    const [u, h] = await Promise.all([
      api.get<GenerationUsage>("/api/generate/usage"),
      api.get<GenerationItem[]>("/api/generate/history"),
    ]);
    setUsage(u);
    setHistory(h);
  }, []);

  useEffect(() => {
    if (user) load().catch(() => {});
  }, [user, load]);

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-400">
        Loading…
      </div>
    );
  }

  const outOfRuns =
    !!usage && !usage.unlimited && (usage.remaining ?? 0) <= 0;

  async function generate() {
    if (!post.trim() || busy) return;
    setBusy(true);
    setError(null);
    setLimitReached(false);
    try {
      const res = await api.post<GenerateResult>("/api/generate", {
        post_content: post,
        platform,
      });
      setReply(res.reply);
      setEditing(false);
      setUsage(res.usage);
      await load();
    } catch (err) {
      if (err instanceof ApiError && (err.status === 429 || err.status === 402)) {
        setLimitReached(true);
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Could not generate a reply.");
      }
    } finally {
      setBusy(false);
    }
  }

  async function copy() {
    if (!reply) return;
    await navigator.clipboard?.writeText(reply);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <AppShell user={user} onLogout={logout}>
      <div className="mb-1 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Response Generator</h1>
        {usage &&
          (usage.unlimited ? (
            <span className="badge bg-green-100 text-green-700">
              Unlimited generations
            </span>
          ) : (
            <span className="badge bg-amber-100 text-amber-700">
              Free trial · {usage.remaining} of {usage.daily_limit} left today
            </span>
          ))}
      </div>
      <p className="mb-6 max-w-2xl text-sm text-slate-500">
        Found a post yourself? Paste it here and I&apos;ll write a reply using
        your services, pricing, and phone number from{" "}
        <Link href="/onboarding" className="text-brand-600 hover:underline">
          Setup
        </Link>
        .
      </p>

      {(limitReached || outOfRuns) && (
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
          <span className="text-sm text-amber-800">
            {error ||
              `You've used your ${usage?.daily_limit ?? 3} free trial generations today.`}{" "}
            Upgrade for <strong>unlimited</strong> custom replies.
          </span>
          <Link href="/billing" className="btn-primary">
            Upgrade
          </Link>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-5">
        <section className="lg:col-span-3">
          <div className="card space-y-4">
            <div className="flex flex-wrap items-end gap-3">
              <div>
                <label className="label">Platform (optional)</label>
                <select
                  className="input"
                  value={platform}
                  onChange={(e) => setPlatform(e.target.value)}
                >
                  <option value="nextdoor">Nextdoor</option>
                  <option value="facebook">Facebook</option>
                  <option value="other">Other</option>
                </select>
              </div>
            </div>
            <div>
              <label className="label">Paste the post you found</label>
              <textarea
                className="input min-h-[140px]"
                placeholder="e.g. “Our water heater died this morning — anyone know a good plumber who can come today??”"
                value={post}
                onChange={(e) => setPost(e.target.value)}
              />
            </div>
            <div className="flex items-center gap-3">
              <button
                className="btn-primary"
                disabled={busy || !post.trim() || outOfRuns}
                onClick={generate}
              >
                {busy ? "Generating…" : "Generate reply"}
              </button>
              {error && !limitReached && (
                <span className="text-sm text-red-600">{error}</span>
              )}
            </div>
          </div>

          {reply && (
            <div className="card mt-6">
              <div className="mb-1 flex items-center justify-between">
                <span className="text-xs font-medium text-slate-500">
                  Your reply
                </span>
                <span className="text-[11px] text-slate-400">
                  Built from your services, pricing &amp; phone
                </span>
              </div>
              {editing ? (
                <textarea
                  className="input min-h-[110px]"
                  value={reply}
                  onChange={(e) => setReply(e.target.value)}
                />
              ) : (
                <p className="whitespace-pre-wrap text-sm text-slate-800">
                  {reply}
                </p>
              )}
              <div className="mt-3 flex flex-wrap gap-2">
                <button className="btn-primary" onClick={copy}>
                  {copied ? "Copied ✓" : "Copy reply"}
                </button>
                <button
                  className="btn-ghost"
                  onClick={() => setEditing((e) => !e)}
                >
                  {editing ? "Done editing" : "Edit"}
                </button>
                <button
                  className="btn-ghost"
                  disabled={busy || outOfRuns}
                  onClick={generate}
                >
                  Regenerate
                </button>
              </div>
            </div>
          )}
        </section>

        <aside className="lg:col-span-2">
          <div className="card">
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
              Recent
            </h3>
            {history.length === 0 ? (
              <p className="text-sm text-slate-400">
                Your generated replies show up here.
              </p>
            ) : (
              <div className="space-y-3">
                {history.map((g) => (
                  <div key={g.id} className="border-b border-slate-100 pb-3 last:border-0 last:pb-0">
                    <p className="line-clamp-2 text-xs text-slate-400">
                      “{g.post_content}”
                    </p>
                    <p className="mt-1 line-clamp-3 text-sm text-slate-700">
                      {g.reply}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </aside>
      </div>
    </AppShell>
  );
}
