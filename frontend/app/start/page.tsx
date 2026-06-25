"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

export default function StartTrialPage() {
  const [form, setForm] = useState({
    business_name: "",
    email: "",
    phone: "",
    nextdoor_handle: "",
  });
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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
        <p className="mb-4 text-center text-sm text-slate-500">
          No card, no password. We&apos;ll email you a one-click sign-in link.
        </p>
        <p className="mb-6 rounded-md bg-brand-50 p-2 text-center text-sm text-brand-700">
          Your free trial includes <strong>1 AI reply per day</strong>. Pick a
          paid plan anytime for more.
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
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button className="btn-primary w-full" disabled={busy}>
            {busy ? "Starting…" : "Start free trial"}
          </button>
          <p className="text-center text-xs text-slate-400">
            By starting a trial you agree to our{" "}
            <Link href="/terms" className="hover:underline">
              Terms
            </Link>{" "}
            and{" "}
            <Link href="/privacy" className="hover:underline">
              Privacy Policy
            </Link>
            .
          </p>
        </form>
      </div>
    </div>
  );
}
