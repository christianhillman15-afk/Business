"use client";

import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { useAuth } from "@/lib/useAuth";
import { api, Notification } from "@/lib/api";

export default function NotificationsPage() {
  const { user, loading, logout } = useAuth();
  const [items, setItems] = useState<Notification[]>([]);

  const refresh = useCallback(async () => {
    setItems(await api.get<Notification[]>("/api/notifications"));
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

  async function markAllRead() {
    await api.post("/api/notifications/read-all");
    await refresh();
  }

  async function markRead(id: number) {
    await api.post(`/api/notifications/${id}/read`);
    await refresh();
  }

  return (
    <AppShell user={user} onLogout={logout}>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Notifications</h1>
        <button className="btn-ghost" onClick={markAllRead}>
          Mark all read
        </button>
      </div>

      {items.length === 0 ? (
        <div className="card text-sm text-slate-500">No notifications yet.</div>
      ) : (
        <div className="space-y-2">
          {items.map((n) => (
            <button
              key={n.id}
              onClick={() => !n.read && markRead(n.id)}
              className={`block w-full rounded-lg border px-4 py-3 text-left ${
                n.read
                  ? "border-slate-200 bg-white"
                  : "border-brand-100 bg-brand-50"
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <span className="font-medium text-slate-800">{n.title}</span>
                {!n.read && (
                  <span className="badge bg-brand-600 text-white">New</span>
                )}
              </div>
              {n.body && (
                <p className="mt-1 text-sm text-slate-500">{n.body}</p>
              )}
              <p className="mt-1 text-xs text-slate-400">
                {new Date(n.created_at).toLocaleString()}
              </p>
            </button>
          ))}
        </div>
      )}
    </AppShell>
  );
}
