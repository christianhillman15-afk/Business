"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { useAuth } from "@/lib/useAuth";
import { api, ConnectedAccount, PricingProfile } from "@/lib/api";

export default function OnboardingPage() {
  const { user, loading, logout } = useAuth();
  const [accounts, setAccounts] = useState<ConnectedAccount[]>([]);
  const [profile, setProfile] = useState<PricingProfile | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!user) return;
    api.get<ConnectedAccount[]>("/api/accounts").then(setAccounts).catch(() => {});
    api.get<PricingProfile>("/api/profile").then(setProfile).catch(() => {});
  }, [user]);

  if (loading || !user || !profile) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-400">
        Loading…
      </div>
    );
  }

  async function connect(provider: "facebook" | "nextdoor") {
    await api.post<ConnectedAccount>("/api/accounts", {
      provider,
      display_name: user!.business_name,
      credential: `demo-connect-${Date.now()}`,
    });
    setAccounts(await api.get<ConnectedAccount[]>("/api/accounts"));
  }

  async function disconnect(id: number) {
    await api.del(`/api/accounts/${id}`);
    setAccounts(await api.get<ConnectedAccount[]>("/api/accounts"));
  }

  async function saveProfile(e: React.FormEvent) {
    e.preventDefault();
    const updated = await api.put<PricingProfile>("/api/profile", {
      trade: profile!.trade,
      service_categories: profile!.service_categories,
      price_list: profile!.price_list,
      phone: profile!.phone,
      target_neighborhoods: profile!.target_neighborhoods,
    });
    setProfile(updated);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  const connected = (p: string) => accounts.find((a) => a.provider === p);

  return (
    <AppShell user={user} onLogout={logout}>
      <h1 className="mb-1 text-2xl font-bold">Setup</h1>
      <p className="mb-6 text-sm text-slate-500">
        Connect your accounts and tell the AI what you do. The bot only engages
        posts that fall within your trade.
      </p>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="card">
          <h2 className="mb-1 text-lg font-semibold">1. Connect accounts</h2>
          <p className="mb-4 text-sm text-slate-500">
            Demo connectors — no real credentials are used. See{" "}
            <code className="text-xs">docs/COMPLIANCE.md</code>.
          </p>
          {(["facebook", "nextdoor"] as const).map((p) => {
            const acc = connected(p);
            return (
              <div
                key={p}
                className="mb-2 flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2"
              >
                <div>
                  <div className="font-medium capitalize">{p}</div>
                  <div className="text-xs text-slate-500">
                    {acc ? (
                      <span className="text-green-600">
                        Connected · {acc.health}
                      </span>
                    ) : (
                      "Not connected"
                    )}
                  </div>
                </div>
                {acc ? (
                  <button className="btn-ghost" onClick={() => disconnect(acc.id)}>
                    Disconnect
                  </button>
                ) : (
                  <button className="btn-primary" onClick={() => connect(p)}>
                    Connect
                  </button>
                )}
              </div>
            );
          })}
        </section>

        <section className="card">
          <h2 className="mb-4 text-lg font-semibold">2. Your trade &amp; pricing</h2>
          <form onSubmit={saveProfile} className="space-y-3">
            <div>
              <label className="label">Trade</label>
              <input
                className="input"
                placeholder="plumbing"
                value={profile.trade ?? ""}
                onChange={(e) =>
                  setProfile({ ...profile, trade: e.target.value })
                }
              />
            </div>
            <div>
              <label className="label">
                Service categories (comma-separated)
              </label>
              <input
                className="input"
                placeholder="leak repair, water heaters, drain cleaning"
                value={profile.service_categories.join(", ")}
                onChange={(e) =>
                  setProfile({
                    ...profile,
                    service_categories: e.target.value
                      .split(",")
                      .map((s) => s.trim())
                      .filter(Boolean),
                  })
                }
              />
              <p className="mt-1 text-xs text-slate-400">
                These define what counts as an in-field lead for you.
              </p>
            </div>
            <div>
              <label className="label">Pricing</label>
              <textarea
                className="input min-h-[70px]"
                placeholder="Service call $89; drain cleaning from $150"
                value={profile.price_list}
                onChange={(e) =>
                  setProfile({ ...profile, price_list: e.target.value })
                }
              />
            </div>
            <div>
              <label className="label">Phone</label>
              <input
                className="input"
                placeholder="(555) 014-7788"
                value={profile.phone ?? ""}
                onChange={(e) =>
                  setProfile({ ...profile, phone: e.target.value })
                }
              />
            </div>
            <div>
              <label className="label">Target neighborhoods (comma-separated)</label>
              <input
                className="input"
                placeholder="Rivertown, Maple Heights"
                value={profile.target_neighborhoods.join(", ")}
                onChange={(e) =>
                  setProfile({
                    ...profile,
                    target_neighborhoods: e.target.value
                      .split(",")
                      .map((s) => s.trim())
                      .filter(Boolean),
                  })
                }
              />
            </div>
            <div className="flex items-center gap-3">
              <button className="btn-primary">Save profile</button>
              {saved && <span className="text-sm text-green-600">Saved ✓</span>}
            </div>
          </form>
        </section>
      </div>
    </AppShell>
  );
}
