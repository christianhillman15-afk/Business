"use client";

import { useEffect, useState } from "react";
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

export default function AdminPage() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);

  useEffect(() => {
    if (!user) return;
    if (user.role !== "admin") {
      router.replace("/dashboard");
      return;
    }
    api.get<AdminStats>("/api/admin/stats").then(setStats).catch(() => {});
    api.get<AdminUser[]>("/api/admin/users").then(setUsers).catch(() => {});
    api
      .get<AuditEntry[]>("/api/admin/audit?limit=15")
      .then(setAudit)
      .catch(() => {});
  }, [user, router]);

  if (loading || !user || user.role !== "admin") {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-400">
        Loading…
      </div>
    );
  }

  return (
    <AppShell user={user} onLogout={logout}>
      <h1 className="mb-1 text-2xl font-bold">Admin console</h1>
      <p className="mb-6 text-sm text-slate-500">
        Platform-wide monitoring, client accounts, and audit trail.
      </p>

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
