"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { useAuth } from "@/lib/useAuth";
import { api, Plan, Subscription } from "@/lib/api";

export default function BillingPage() {
  const { user, loading, logout } = useAuth();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [sub, setSub] = useState<Subscription | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    api.get<Plan[]>("/api/plans").then(setPlans).catch(() => {});
    api.get<Subscription>("/api/subscription").then(setSub).catch(() => {});
  }, [user]);

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-400">
        Loading…
      </div>
    );
  }

  async function selectPlan(code: string) {
    setBusy(code);
    try {
      const res = await api.post<{
        subscription: Subscription;
        checkout_url: string | null;
      }>("/api/subscription/select", { plan_code: code });
      if (res.checkout_url) {
        window.location.href = res.checkout_url; // Stripe Checkout
        return;
      }
      setSub(res.subscription);
    } finally {
      setBusy(null);
    }
  }

  return (
    <AppShell user={user} onLogout={logout}>
      <h1 className="mb-1 text-2xl font-bold">Billing</h1>
      <p className="mb-6 text-sm text-slate-500">
        Plans are billed monthly by daily post quota. Status:{" "}
        <span className="font-medium capitalize">{sub?.status ?? "—"}</span>
        {sub && (
          <>
            {" "}· current plan:{" "}
            <span className="font-medium capitalize">{sub.plan_code}</span>
          </>
        )}
      </p>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {plans.map((p) => {
          const current = sub?.plan_code === p.code;
          return (
            <div
              key={p.code}
              className={`card flex flex-col ${
                current ? "ring-2 ring-brand-500" : ""
              }`}
            >
              <div className="text-lg font-semibold">{p.name}</div>
              <div className="mt-1 text-3xl font-bold">
                ${p.price_monthly}
                <span className="text-sm font-normal text-slate-400">/mo</span>
              </div>
              <div className="mt-2 text-sm text-slate-500">
                {p.daily_post_quota} AI posts / day
              </div>
              <button
                className={`mt-4 ${current ? "btn-ghost" : "btn-primary"}`}
                disabled={current || busy === p.code}
                onClick={() => selectPlan(p.code)}
              >
                {current
                  ? "Current plan"
                  : busy === p.code
                  ? "Switching…"
                  : "Choose plan"}
              </button>
            </div>
          );
        })}
      </div>

      <p className="mt-6 text-xs text-slate-400">
        Using the built-in mock billing provider. Set{" "}
        <code>STRIPE_SECRET_KEY</code> to enable real Stripe checkout.
      </p>
    </AppShell>
  );
}
