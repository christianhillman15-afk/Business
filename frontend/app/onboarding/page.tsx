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

  async function connectOAuth(provider: "facebook" | "nextdoor") {
    // Official authorize flow — no password is ever entered in LeadPilot.
    const res = await api.get<{ authorize_url: string }>(
      `/api/accounts/oauth/${provider}/start`,
    );
    window.location.href = res.authorize_url;
  }

  async function connectManaged(provider: "facebook" | "nextdoor") {
    await api.post<ConnectedAccount>("/api/accounts", {
      provider,
      auth_method: "managed_business_page",
      display_name: user!.business_name,
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
            We never ask for or store your password. Connect with the official
            authorize button, or have us set up a Business Page for you.
          </p>
          {(["facebook", "nextdoor"] as const).map((p) => {
            const acc = connected(p);
            const provisioning = acc?.health === "provisioning";
            return (
              <div
                key={p}
                className="mb-3 rounded-lg border border-slate-200 px-3 py-3"
              >
                <div className="mb-2 flex items-center justify-between">
                  <span className="font-medium capitalize">{p}</span>
                  {acc ? (
                    provisioning ? (
                      <span className="badge bg-amber-100 text-amber-700">
                        Setting up your page…
                      </span>
                    ) : (
                      <span className="badge bg-green-100 text-green-700">
                        Connected ·{" "}
                        {acc.auth_method === "managed_business_page"
                          ? "managed page"
                          : "authorized"}
                      </span>
                    )
                  ) : (
                    <span className="badge bg-slate-100 text-slate-500">
                      Not connected
                    </span>
                  )}
                </div>

                {acc ? (
                  <button className="btn-ghost" onClick={() => disconnect(acc.id)}>
                    {provisioning ? "Cancel request" : "Disconnect"}
                  </button>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    <button
                      className="btn-primary"
                      onClick={() => connectOAuth(p)}
                    >
                      Connect with {p === "facebook" ? "Facebook" : "Nextdoor"}
                    </button>
                    <button
                      className="btn-ghost"
                      onClick={() => connectManaged(p)}
                    >
                      Set up a Business Page for me
                    </button>
                  </div>
                )}
              </div>
            );
          })}
          <p className="mt-1 text-xs text-slate-400">
            “Connect” uses the platform&apos;s official authorization — no
            password is shared. “Set up a Business Page” means we provision a
            dedicated page for your business; you don&apos;t connect any personal
            account.
          </p>
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
