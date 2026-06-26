"use client";

import { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { useAuth } from "@/lib/useAuth";
import { api } from "@/lib/api";

export default function FreeTrialPage() {
  const { user, loading, logout } = useAuth();
  const [form, setForm] = useState({
    name: "",
    business_name: "",
    email: "",
    phone: "",
  });
  const [done, setDone] = useState<typeof form | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function set(k: keyof typeof form, v: string) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-400">
        Loading…
      </div>
    );
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/auth/start-trial", {
        email: form.email,
        name: form.name || null,
        business_name: form.business_name || null,
        phone: form.phone || null,
      });
      setDone(form);
      setForm({ name: "", business_name: "", email: "", phone: "" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell user={user} onLogout={logout}>
      <h1 className="mb-1 text-2xl font-bold">Free Trial</h1>
      <p className="mb-6 max-w-2xl text-sm text-slate-500">
        Start a <strong>7-day free trial</strong> for a business — yourself or a
        provider you&apos;re referring. We email them a one-click sign-in link.
        The trial includes <strong>1 AI reply per day</strong>; they can pick a
        paid plan anytime.
      </p>

      <div className="grid gap-6 lg:grid-cols-5">
        <section className="lg:col-span-3">
          <div className="card-glow">
            {done ? (
              <div className="text-center">
                <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-green-100 text-2xl">
                  ✅
                </div>
                <h2 className="text-lg font-bold">Trial started</h2>
                <p className="mx-auto mt-1 max-w-md text-sm text-slate-500">
                  A one-click sign-in link is on its way to{" "}
                  <strong>{done.email}</strong>
                  {done.name ? (
                    <>
                      {" "}
                      for <strong>{done.name}</strong>
                    </>
                  ) : null}
                  {done.business_name ? (
                    <>
                      {" "}
                      at <strong>{done.business_name}</strong>
                    </>
                  ) : null}
                  .
                </p>
                <button
                  className="btn-primary mt-5"
                  onClick={() => setDone(null)}
                >
                  Start another trial
                </button>
              </div>
            ) : (
              <form onSubmit={submit} className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="label">Name</label>
                    <input
                      className="input"
                      value={form.name}
                      onChange={(e) => set("name", e.target.value)}
                      placeholder="Jordan Rivers"
                    />
                  </div>
                  <div>
                    <label className="label">Business name</label>
                    <input
                      className="input"
                      value={form.business_name}
                      onChange={(e) => set("business_name", e.target.value)}
                      placeholder="Rivertown Plumbing Co."
                    />
                  </div>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="label">Email</label>
                    <input
                      className="input"
                      type="email"
                      required
                      value={form.email}
                      onChange={(e) => set("email", e.target.value)}
                      placeholder="jordan@rivertownplumbing.com"
                    />
                  </div>
                  <div>
                    <label className="label">Phone</label>
                    <input
                      className="input"
                      value={form.phone}
                      onChange={(e) => set("phone", e.target.value)}
                      placeholder="(555) 014-7788"
                    />
                  </div>
                </div>
                {error && <p className="text-sm text-red-600">{error}</p>}
                <button className="btn-cta-dark w-full sm:w-auto" disabled={busy}>
                  {busy ? "Starting…" : "Start free trial →"}
                </button>
                <p className="text-xs text-slate-400">
                  No card required. We never ask for a password — sign-in is by
                  one-click email link.
                </p>
              </form>
            )}
          </div>
        </section>

        <aside className="lg:col-span-2">
          <div className="card h-full">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
              What they get
            </h3>
            <ul className="mt-3 space-y-3 text-sm text-slate-600">
              {[
                "AI scans local Nextdoor & Facebook for jobs in their trade",
                "A ready-to-send reply with their services, pricing & phone",
                "Every new lead texted straight to their phone",
                "1 AI reply per day, free for 7 days",
              ].map((t) => (
                <li key={t} className="flex gap-2">
                  <span className="text-green-500">✓</span>
                  <span>{t}</span>
                </li>
              ))}
            </ul>
          </div>
        </aside>
      </div>
    </AppShell>
  );
}
