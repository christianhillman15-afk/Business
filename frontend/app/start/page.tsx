"use client";

import { useEffect, useState } from "react";
import { api, Plan } from "@/lib/api";

export default function StartTrialPage() {
  const [form, setForm] = useState({
    business_name: "",
    email: "",
    phone: "",
    nextdoor_handle: "",
    plan_code: "growth",
  });
  const [plans, setPlans] = useState<Plan[]>([]);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get<Plan[]>("/api/plans").then(setPlans).catch(() => {});
  }, []);

  function set(k: keyof typeof form, v: string) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/auth/start-trial", {
        email: form.email,
        business_name: form.business_name || null,
        phone: form.phone || null,
        nextdoor_handle: form.nextdoor_handle || null,
        plan_code: form.plan_code,
      });
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <div className="card max-w-sm text-center">
          <div className="mb-2 text-3xl">📬</div>
          <h1 className="mb-1 text-xl font-bold">Check your email</h1>
          <p className="text-sm text-slate-500">
            We sent a one-click sign-in link to <strong>{form.email}</strong>.
            No password needed — click it to start your 7-day free trial.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <h1 className="mb-1 text-center text-2xl font-bold text-brand-700">
          Start your 7-day free trial
        </h1>
        <p className="mb-6 text-center text-sm text-slate-500">
          No card, no password. We&apos;ll email you a one-click sign-in link.
        </p>
        <form onSubmit={submit} className="card space-y-4">
          <div>
            <label className="label">Business name</label>
            <input
              className="input"
              value={form.business_name}
              onChange={(e) => set("business_name", e.target.value)}
              placeholder="Rivertown Plumbing Co."
            />
          </div>
          <div>
            <label className="label">Email</label>
            <input
              className="input"
              type="email"
              required
              value={form.email}
              onChange={(e) => set("email", e.target.value)}
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
          <div>
            <label className="label">Nextdoor handle</label>
            <input
              className="input"
              value={form.nextdoor_handle}
              onChange={(e) => set("nextdoor_handle", e.target.value)}
              placeholder="your Nextdoor profile / neighborhood"
            />
          </div>
          <div>
            <label className="label">Plan</label>
            <select
              className="input"
              value={form.plan_code}
              onChange={(e) => set("plan_code", e.target.value)}
            >
              {plans.map((p) => (
                <option key={p.code} value={p.code}>
                  {p.name} — ${p.price_monthly}/mo · {p.daily_post_quota}/day
                </option>
              ))}
            </select>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button className="btn-primary w-full" disabled={busy}>
            {busy ? "Starting…" : "Start free trial"}
          </button>
        </form>
      </div>
    </div>
  );
}
