"use client";

import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { useAuth } from "@/lib/useAuth";
import { api, Broadcast } from "@/lib/api";

export default function BroadcastPage() {
  const { user, loading, logout } = useAuth();
  const [posts, setPosts] = useState<Broadcast[]>([]);
  const [provider, setProvider] = useState<"nextdoor" | "facebook">("nextdoor");
  const [topic, setTopic] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setPosts(await api.get<Broadcast[]>("/api/broadcast"));
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

  async function draft() {
    setBusy(true);
    try {
      await api.post("/api/broadcast/draft", { provider, topic: topic || null });
      setTopic("");
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell user={user} onLogout={logout}>
      <h1 className="mb-1 text-2xl font-bold">Business Posts</h1>
      <p className="mb-6 max-w-2xl text-sm text-slate-500">
        Proactively reach nearby neighbors. On Nextdoor this is the AI&apos;s
        compliant way to post for you — it publishes a <strong>new</strong>{" "}
        Business Post through Nextdoor&apos;s official API (replying on other
        people&apos;s posts has no API, so those stay one-tap-assisted on the
        dashboard). You review every draft before it goes out.
      </p>

      <div className="card mb-8">
        <h2 className="mb-3 text-lg font-semibold">Draft a new post</h2>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="label">Platform</label>
            <select
              className="input"
              value={provider}
              onChange={(e) =>
                setProvider(e.target.value as "nextdoor" | "facebook")
              }
            >
              <option value="nextdoor">Nextdoor</option>
              <option value="facebook">Facebook</option>
            </select>
          </div>
          <div className="flex-1">
            <label className="label">Theme / offer (optional)</label>
            <input
              className="input"
              placeholder="e.g. winter pipe checkups, $50 off drain cleaning"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
            />
          </div>
          <button className="btn-primary" onClick={draft} disabled={busy}>
            {busy ? "Drafting…" : "Generate draft"}
          </button>
        </div>
      </div>

      <div className="space-y-3">
        {posts.length === 0 && (
          <div className="card text-sm text-slate-500">
            No business posts yet. Generate a draft above.
          </div>
        )}
        {posts.map((p) => (
          <BroadcastCard key={p.id} post={p} onChange={refresh} />
        ))}
      </div>
    </AppShell>
  );
}

function BroadcastCard({
  post,
  onChange,
}: {
  post: Broadcast;
  onChange: () => void;
}) {
  const [text, setText] = useState(post.body_text);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const posted = post.status === "posted";

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
      <div className="mb-2 flex items-center gap-2 text-xs text-slate-500">
        <span className="badge bg-brand-50 capitalize text-brand-700">
          {post.provider}
        </span>
        {posted ? (
          <span className="badge bg-green-100 text-green-700">Posted</span>
        ) : (
          <span className="badge bg-amber-100 text-amber-700">Draft</span>
        )}
      </div>

      {editing ? (
        <textarea
          className="input min-h-[90px]"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
      ) : (
        <p className="text-sm text-slate-800">{post.body_text}</p>
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
                    await api.put(`/api/broadcast/${post.id}`, {
                      body_text: text,
                    });
                    setEditing(false);
                  })
                }
              >
                Save
              </button>
              <button
                className="btn-ghost"
                onClick={() => {
                  setText(post.body_text);
                  setEditing(false);
                }}
              >
                Cancel
              </button>
            </>
          ) : (
            <>
              <button
                className="btn-primary"
                disabled={busy}
                onClick={() => act(() => api.post(`/api/broadcast/${post.id}/publish`))}
              >
                Publish to {post.provider}
              </button>
              <button className="btn-ghost" onClick={() => setEditing(true)}>
                Edit
              </button>
              <button
                className="btn-ghost"
                disabled={busy}
                onClick={() => act(() => api.del(`/api/broadcast/${post.id}`))}
              >
                Delete
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
