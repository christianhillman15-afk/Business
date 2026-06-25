"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { useAuth } from "@/lib/useAuth";
import { api, clearToken, User } from "@/lib/api";

const TIMEZONES = [
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "America/Phoenix",
  "America/Anchorage",
  "Pacific/Honolulu",
];

export default function SettingsPage() {
  const { user, loading, logout, setUser } = useAuth();
  const router = useRouter();
  const [form, setForm] = useState({
    business_name: "",
    phone: "",
    nextdoor_handle: "",
    timezone: "America/New_York",
  });
  const [savedMsg, setSavedMsg] = useState<string | null>(null);
  const [pw, setPw] = useState({ current_password: "", new_password: "" });
  const [pwMsg, setPwMsg] = useState<string | null>(null);

  useEffect(() => {
    if (user) {
      setForm({
        business_name: user.business_name ?? "",
        phone: user.phone ?? "",
        nextdoor_handle: user.nextdoor_handle ?? "",
        timezone: user.timezone,
      });
    }
  }, [user]);

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-400">
        Loading…
      </div>
    );
  }

  async function saveProfile(e: React.FormEvent) {
    e.preventDefault();
    setSavedMsg(null);
    const updated = await api.patch<User>("/api/account", form);
    setUser(updated);
    setSavedMsg("Saved ✓");
    setTimeout(() => setSavedMsg(null), 2000);
  }

  async function savePassword(e: React.FormEvent) {
    e.preventDefault();
    setPwMsg(null);
    try {
      await api.post("/api/account/password", {
        current_password: pw.current_password || null,
        new_password: pw.new_password,
      });
      setPw({ current_password: "", new_password: "" });
      setPwMsg("Password updated ✓");
    } catch (err) {
      setPwMsg(err instanceof Error ? err.message : "Could not update password");
    }
  }

  async function deleteAccount() {
    if (
      !window.confirm(
        "Delete your account and all data permanently? This cannot be undone.",
      )
    )
      return;
    await api.del("/api/account");
    clearToken();
    router.replace("/login");
  }

  return (
    <AppShell user={user} onLogout={logout}>
      <h1 className="mb-6 text-2xl font-bold">Settings</h1>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="card">
          <h2 className="mb-4 text-lg font-semibold">Profile</h2>
          <form onSubmit={saveProfile} className="space-y-3">
            <div>
              <label className="label">Business name</label>
              <input
                className="input"
                value={form.business_name}
                onChange={(e) =>
                  setForm({ ...form, business_name: e.target.value })
                }
              />
            </div>
            <div>
              <label className="label">Contact phone</label>
              <input
                className="input"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
              />
            </div>
            <div>
              <label className="label">Nextdoor handle</label>
              <input
                className="input"
                value={form.nextdoor_handle}
                onChange={(e) =>
                  setForm({ ...form, nextdoor_handle: e.target.value })
                }
              />
            </div>
            <div>
              <label className="label">Timezone (quota resets at local midnight)</label>
              <select
                className="input"
                value={form.timezone}
                onChange={(e) => setForm({ ...form, timezone: e.target.value })}
              >
                {TIMEZONES.map((tz) => (
                  <option key={tz} value={tz}>
                    {tz}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-3">
              <button className="btn-primary">Save</button>
              {savedMsg && (
                <span className="text-sm text-green-600">{savedMsg}</span>
              )}
            </div>
          </form>
        </section>

        <div className="space-y-6">
          <section className="card">
            <h2 className="mb-1 text-lg font-semibold">Password</h2>
            <p className="mb-4 text-sm text-slate-500">
              Optional — you can also sign in with a one-click email link.
            </p>
            <form onSubmit={savePassword} className="space-y-3">
              <div>
                <label className="label">Current password (if you have one)</label>
                <input
                  className="input"
                  type="password"
                  value={pw.current_password}
                  onChange={(e) =>
                    setPw({ ...pw, current_password: e.target.value })
                  }
                />
              </div>
              <div>
                <label className="label">New password</label>
                <input
                  className="input"
                  type="password"
                  minLength={8}
                  required
                  value={pw.new_password}
                  onChange={(e) =>
                    setPw({ ...pw, new_password: e.target.value })
                  }
                />
              </div>
              <div className="flex items-center gap-3">
                <button className="btn-primary">Update password</button>
                {pwMsg && <span className="text-sm text-slate-600">{pwMsg}</span>}
              </div>
            </form>
          </section>

          <section className="card border-red-200">
            <h2 className="mb-1 text-lg font-semibold text-red-700">
              Danger zone
            </h2>
            <p className="mb-4 text-sm text-slate-500">
              Permanently delete your account, connected accounts, and all leads.
            </p>
            <button
              className="btn bg-red-600 text-white hover:bg-red-700"
              onClick={deleteAccount}
            >
              Delete my account
            </button>
          </section>
        </div>
      </div>
    </AppShell>
  );
}
