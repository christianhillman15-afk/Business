"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { useAuth } from "@/lib/useAuth";
import { api } from "@/lib/api";

interface AdminStats {
  providers: number;
  leads: number;
  posted_replies: number;
  open_tickets: number;
  escalated_tickets: number;
  recruits_contacted: number;
}
interface AdminUser {
  id: number;
  email: string;
  business_name: string | null;
  role: string;
  automation_enabled: boolean;
  subscription: { plan_code: string; status: string } | null;
}
interface AuditEntry {
  id: number;
  action: string;
  detail: string | null;
  created_at: string;
}
interface Recruit {
  id: number;
  provider: string;
  contact_name: string | null;
  profile_url: string | null;
  email: string | null;
  converted_user_id: number | null;
  message_sent: boolean;
  trial_signup_at: string | null;
}
interface Provisioning {
  id: number;
  provider: string;
  business_name: string | null;
  email: string;
  health: string;
}

export default function AdminPage() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [recruits, setRecruits] = useState<Recruit[]>([]);
  const [provisioning, setProvisioning] = useState<Provisioning[]>([]);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(() => {
    api.get<AdminStats>("/api/admin/stats").then(setStats).catch(() => {});
    api.get<AdminUser[]>("/api/admin/users").then(setUsers).catch(() => {});
    api.get<AuditEntry[]>("/api/admin/audit?limit=15").then(setAudit).catch(() => {});
    api.get<Recruit[]>("/api/admin/recruits").then(setRecruits).catch(() => {});
    api
      .get<Provisioning[]>("/api/admin/provisioning")
      .then(setProvisioning)
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!user) return;
    if (user.role !== "admin") {
      router.replace("/dashboard");
      return;
    }
    load();
  }, [user, router, load]);

  async function runJob(path: string, key: string) {
    setBusy(key);
    try {
      await api.post(path);
      load();
    } finally {
      setBusy(null);
    }
  }

  async function activate(id: number) {
    setBusy(`activate-${id}`);
    try {
      await api.post(`/api/admin/accounts/${id}/activate`);
      load();
    } finally {
      setBusy(null);
    }
  }

  async function convertRecruit(id: number) {
    const email = window.prompt("Prospect's email to start their trial:");
    if (!email) return;
    setBusy(`convert-${id}`);
    try {
      await api.post(`/api/admin/recruits/${id}/convert`, { email });
      load();
    } finally {
      setBusy(null);
    }
  }

  if (loading || !user || user.role !== "admin") {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-400">
        Loading…
      </div>
    );
  }

  return (
    <AppShell user={user} onLogout={logout}>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Admin console</h1>
          <p className="text-sm text-slate-500">
            Platform-wide monitoring, recruiting, and audit trail.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            className="btn-ghost"
            disabled={busy === "discovery"}
            onClick={() => runJob("/api/admin/discovery/run-all", "discovery")}
          >
            {busy === "discovery" ? "Scanning…" : "Run discovery (all)"}
          </button>
          <button
            className="btn-primary"
            disabled={busy === "recruit"}
            onClick={() => runJob("/api/admin/recruiting/run", "recruit")}
          >
            {busy === "recruit" ? "Recruiting…" : "Run recruiter"}
          </button>
        </div>
      </div>

      {stats && (
        <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          <Stat label="Providers" value={stats.providers} />
          <Stat label="Leads" value={stats.leads} />
          <Stat label="Posted" value={stats.posted_replies} />
          <Stat label="Open tickets" value={stats.open_tickets} />
          <Stat label="Escalated" value={stats.escalated_tickets} />
          <Stat label="Recruits" value={stats.recruits_contacted} />
        </div>
      )}

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-semibold">Clients</h2>
        <div className="card overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-400">
              <tr>
                <th className="px-4 py-2">Business</th>
                <th className="px-4 py-2">Email</th>
                <th className="px-4 py-2">Role</th>
                <th className="px-4 py-2">Plan</th>
                <th className="px-4 py-2">Automation</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-t border-slate-100">
                  <td className="px-4 py-2">{u.business_name || "—"}</td>
                  <td className="px-4 py-2">{u.email}</td>
                  <td className="px-4 py-2 capitalize">{u.role}</td>
                  <td className="px-4 py-2 capitalize">
                    {u.subscription?.plan_code ?? "—"}
                  </td>
                  <td className="px-4 py-2">
                    {u.automation_enabled ? "ON" : "OFF"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-semibold">
          Managed Business Page setups{" "}
          <span className="text-sm font-normal text-slate-400">
            ({provisioning.length} pending)
          </span>
        </h2>
        {provisioning.length === 0 ? (
          <div className="card text-sm text-slate-500">
            No pending setups. When a client picks “Set up a Business Page for
            me,” it appears here for the team to provision and activate.
          </div>
        ) : (
          <div className="card space-y-2 text-sm">
            {provisioning.map((p) => (
              <div
                key={p.id}
                className="flex items-center justify-between border-b border-slate-100 py-2 last:border-0"
              >
                <div>
                  <span className="font-medium text-slate-700">
                    {p.business_name || p.email}
                  </span>{" "}
                  <span className="text-slate-400">
                    · {p.provider} · {p.email}
                  </span>
                </div>
                <button
                  className="btn-primary"
                  disabled={busy === `activate-${p.id}`}
                  onClick={() => activate(p.id)}
                >
                  {busy === `activate-${p.id}` ? "Activating…" : "Mark live"}
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-semibold">
          Trial Recruiter{" "}
          <span className="text-sm font-normal text-slate-400">
            ({recruits.length} contacted)
          </span>
        </h2>
        {recruits.length === 0 ? (
          <div className="card text-sm text-slate-500">
            No recruiting activity yet. Click <strong>Run recruiter</strong> to
            queue trial pitches to other local providers.
          </div>
        ) : (
          <div className="card space-y-1 text-sm">
            {recruits.map((r) => (
              <div
                key={r.id}
                className="flex items-center justify-between border-b border-slate-100 py-1 last:border-0"
              >
                <span className="font-medium text-slate-700">
                  {r.contact_name || r.profile_url}
                </span>
                <span className="flex items-center gap-2 text-xs">
                  {r.converted_user_id ? (
                    <span className="badge bg-green-100 text-green-700">
                      Trial started{r.email ? ` · ${r.email}` : ""}
                    </span>
                  ) : (
                    <>
                      <span className="badge bg-brand-50 text-brand-700">
                        {r.message_sent ? "Pitched" : "Queued"}
                      </span>
                      <button
                        className="btn-ghost px-2 py-1 text-xs"
                        disabled={busy === `convert-${r.id}`}
                        onClick={() => convertRecruit(r.id)}
                      >
                        {busy === `convert-${r.id}` ? "…" : "Convert → trial"}
                      </button>
                    </>
                  )}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Recent activity</h2>
        <div className="card space-y-1 text-sm">
          {audit.map((a) => (
            <div
              key={a.id}
              className="flex justify-between border-b border-slate-100 py-1 last:border-0"
            >
              <span className="font-medium text-slate-700">{a.action}</span>
              <span className="text-slate-400">{a.detail}</span>
            </div>
          ))}
          {audit.length === 0 && (
            <p className="text-slate-400">No activity yet.</p>
          )}
        </div>
      </section>
    </AppShell>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="card">
      <div className="text-xs uppercase tracking-wide text-slate-400">
        {label}
      </div>
      <div className="mt-1 text-2xl font-bold">{value}</div>
    </div>
  );
}
