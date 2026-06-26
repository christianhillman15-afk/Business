"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/useAuth";
import { api, ClientDetail, ClientSummary } from "@/lib/api";

const TABS = ["Profile", "Services", "Status", "Claim", "Contacts"] as const;
type Tab = (typeof TABS)[number];

export default function AdminPage() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const [clients, setClients] = useState<ClientSummary[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<ClientDetail | null>(null);
  const [tab, setTab] = useState<Tab>("Profile");
  const [query, setQuery] = useState("");

  const loadClients = useCallback(async () => {
    const list = await api.get<ClientSummary[]>("/api/admin/clients");
    setClients(list);
    setSelectedId((prev) => prev ?? (list[0]?.id ?? null));
  }, []);

  useEffect(() => {
    if (!user) return;
    if (user.role !== "admin") {
      router.replace("/login");
      return;
    }
    loadClients().catch(() => {});
  }, [user, router, loadClients]);

  useEffect(() => {
    if (selectedId == null) return;
    api
      .get<ClientDetail>(`/api/admin/clients/${selectedId}`)
      .then(setDetail)
      .catch(() => {});
  }, [selectedId]);

  const refreshDetail = useCallback(async () => {
    if (selectedId == null) return;
    setDetail(await api.get<ClientDetail>(`/api/admin/clients/${selectedId}`));
    await loadClients();
  }, [selectedId, loadClients]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return clients;
    return clients.filter((c) =>
      [c.business_name, c.contact_name, c.city, c.state]
        .filter(Boolean)
        .some((v) => v!.toLowerCase().includes(q)),
    );
  }, [clients, query]);

  if (loading || !user || user.role !== "admin") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 text-slate-400">
        Loading…
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-100">
      {/* Admin chrome — its own bar, separate from the customer app */}
      <header className="sticky top-0 z-40 border-b border-slate-800 bg-slate-900 text-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="text-lg font-extrabold tracking-tight">
              <span className="text-grad">Lead</span>Pilot
            </span>
            <span className="rounded-md bg-white/10 px-2 py-0.5 text-xs font-semibold uppercase tracking-wide">
              Admin
            </span>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="hidden text-slate-300 sm:inline">{user.email}</span>
            <Link href="/dashboard" className="text-slate-300 hover:text-white">
              Customer view
            </Link>
            <button
              className="rounded-md border border-white/20 px-3 py-1.5 hover:bg-white/10"
              onClick={logout}
            >
              Log out
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-6 px-4 py-6 lg:grid-cols-[320px_1fr]">
        {/* Client list */}
        <aside>
          <div className="mb-3 flex items-center justify-between">
            <h1 className="text-lg font-bold text-slate-900">
              Clients{" "}
              <span className="text-sm font-normal text-slate-400">
                ({clients.length})
              </span>
            </h1>
          </div>
          <input
            className="input mb-3"
            placeholder="Search name, city, state…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div className="space-y-2">
            {filtered.map((c) => (
              <button
                key={c.id}
                onClick={() => {
                  setSelectedId(c.id);
                  setTab("Profile");
                }}
                className={`w-full rounded-xl border p-3 text-left transition ${
                  c.id === selectedId
                    ? "border-indigo-300 bg-white shadow-sm ring-1 ring-indigo-200"
                    : "border-slate-200 bg-white hover:border-slate-300"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate font-semibold text-slate-800">
                    {c.business_name || c.contact_name || "Unnamed client"}
                  </span>
                  <StatusDot status={c.client_status} />
                </div>
                <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
                  {(c.city || c.state) && (
                    <span>
                      {[c.city, c.state].filter(Boolean).join(", ")}
                    </span>
                  )}
                  {c.trial_active && (
                    <span className="badge bg-amber-100 text-amber-700">
                      Trial · {c.trial_days_left ?? "—"}d left
                    </span>
                  )}
                  {c.claimed_by && (
                    <span className="badge bg-indigo-100 text-indigo-700">
                      🔒 {c.claimed_by}
                    </span>
                  )}
                </div>
              </button>
            ))}
            {filtered.length === 0 && (
              <p className="text-sm text-slate-400">No clients match “{query}”.</p>
            )}
          </div>
        </aside>

        {/* Detail */}
        <main>
          {!detail ? (
            <div className="card text-sm text-slate-500">
              Select a client to view their profile.
            </div>
          ) : (
            <div>
              <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-2xl font-bold text-slate-900">
                    {detail.business_name || "Unnamed client"}
                  </h2>
                  <p className="text-sm text-slate-500">
                    {detail.contact_name ? `${detail.contact_name} · ` : ""}
                    {detail.email}
                  </p>
                </div>
                <StatusDot status={detail.client_status} large />
              </div>

              <div className="mb-4 flex flex-wrap gap-1 border-b border-slate-200">
                {TABS.map((t) => (
                  <button
                    key={t}
                    onClick={() => setTab(t)}
                    className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${
                      tab === t
                        ? "border-indigo-600 text-indigo-700"
                        : "border-transparent text-slate-500 hover:text-slate-800"
                    }`}
                  >
                    {t}
                    {t === "Contacts" && detail.contacts.length > 0
                      ? ` (${detail.contacts.length})`
                      : ""}
                  </button>
                ))}
              </div>

              {tab === "Profile" && (
                <ProfileTab detail={detail} onSaved={refreshDetail} />
              )}
              {tab === "Services" && (
                <ServicesTab detail={detail} onSaved={refreshDetail} />
              )}
              {tab === "Status" && (
                <StatusTab detail={detail} onSaved={refreshDetail} />
              )}
              {tab === "Claim" && (
                <ClaimTab detail={detail} me={user.email} onSaved={refreshDetail} />
              )}
              {tab === "Contacts" && (
                <ContactsTab detail={detail} onSaved={refreshDetail} />
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

function StatusDot({ status, large }: { status: string; large?: boolean }) {
  const enabled = status !== "disabled";
  return (
    <span
      className={`badge ${
        enabled ? "bg-green-100 text-green-700" : "bg-slate-200 text-slate-500"
      } ${large ? "text-sm" : ""}`}
    >
      {enabled ? "Enabled" : "Disabled"}
    </span>
  );
}

function Saved({ show }: { show: boolean }) {
  return show ? <span className="text-sm text-green-600">Saved ✓</span> : null;
}

async function patchClient(id: number, body: Record<string, unknown>) {
  return api.patch<ClientDetail>(`/api/admin/clients/${id}`, body);
}

function ProfileTab({
  detail,
  onSaved,
}: {
  detail: ClientDetail;
  onSaved: () => Promise<void>;
}) {
  const [f, setF] = useState({
    business_name: detail.business_name ?? "",
    contact_name: detail.contact_name ?? "",
    phone: detail.phone ?? "",
    city: detail.city ?? "",
    state: detail.state ?? "",
    service_radius_miles: detail.service_radius_miles ?? "",
    client_notes: detail.client_notes ?? "",
    bot_notes: detail.bot_notes ?? "",
  });
  const [saved, setSaved] = useState(false);

  async function save() {
    await patchClient(detail.id, {
      ...f,
      service_radius_miles:
        f.service_radius_miles === "" ? null : Number(f.service_radius_miles),
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
    await onSaved();
  }

  return (
    <div className="card space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Company name">
          <input className="input" value={f.business_name} onChange={(e) => setF({ ...f, business_name: e.target.value })} />
        </Field>
        <Field label="Contact name">
          <input className="input" value={f.contact_name} onChange={(e) => setF({ ...f, contact_name: e.target.value })} />
        </Field>
        <Field label="City">
          <input className="input" value={f.city} onChange={(e) => setF({ ...f, city: e.target.value })} />
        </Field>
        <Field label="State">
          <input className="input" value={f.state} onChange={(e) => setF({ ...f, state: e.target.value })} />
        </Field>
        <Field label="Search radius outside city (miles)">
          <input
            className="input"
            type="number"
            min={0}
            value={f.service_radius_miles}
            onChange={(e) => setF({ ...f, service_radius_miles: e.target.value })}
          />
        </Field>
        <Field label="Phone">
          <input className="input" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} />
        </Field>
      </div>
      <Field label="Client notes (the team's notes about this client)">
        <textarea className="input min-h-[80px]" value={f.client_notes} onChange={(e) => setF({ ...f, client_notes: e.target.value })} />
      </Field>
      <Field label="Bot notes (how they feel about the product, how they text, overall description)">
        <textarea className="input min-h-[80px]" value={f.bot_notes} onChange={(e) => setF({ ...f, bot_notes: e.target.value })} />
      </Field>
      <div className="flex items-center gap-3">
        <button className="btn-primary" onClick={save}>Save profile</button>
        <Saved show={saved} />
      </div>
    </div>
  );
}

function ServicesTab({
  detail,
  onSaved,
}: {
  detail: ClientDetail;
  onSaved: () => Promise<void>;
}) {
  const [trade, setTrade] = useState(detail.trade ?? "");
  const [services, setServices] = useState(detail.services.join("\n"));
  const [saved, setSaved] = useState(false);

  async function save() {
    const list = services
      .split(/[\n,]/)
      .map((s) => s.trim())
      .filter(Boolean);
    await patchClient(detail.id, { trade, services: list });
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
    await onSaved();
  }

  return (
    <div className="card space-y-4">
      <Field label="Trade">
        <input className="input" placeholder="plumbing" value={trade} onChange={(e) => setTrade(e.target.value)} />
      </Field>
      <Field label="Everything in their field of services (one per line)">
        <textarea
          className="input min-h-[160px]"
          placeholder={"leak repair\nwater heater install\ndrain cleaning\ntoilet repair"}
          value={services}
          onChange={(e) => setServices(e.target.value)}
        />
        <p className="mt-1 text-xs text-slate-400">
          The bot asks the client to list everything they do; this is what counts
          as an in-field lead for them.
        </p>
      </Field>
      <div className="flex flex-wrap gap-1.5">
        {detail.services.map((s) => (
          <span key={s} className="badge bg-slate-100 text-slate-600">{s}</span>
        ))}
      </div>
      <div className="flex items-center gap-3">
        <button className="btn-primary" onClick={save}>Save services</button>
        <Saved show={saved} />
      </div>
    </div>
  );
}

function StatusTab({
  detail,
  onSaved,
}: {
  detail: ClientDetail;
  onSaved: () => Promise<void>;
}) {
  const [days, setDays] = useState(String(detail.trial_days_left ?? ""));
  const [busy, setBusy] = useState(false);

  async function setStatus(status: string) {
    setBusy(true);
    try {
      await patchClient(detail.id, { client_status: status });
      await onSaved();
    } finally {
      setBusy(false);
    }
  }
  async function setTrial(body: Record<string, unknown>) {
    setBusy(true);
    try {
      await api.patch<ClientDetail>(`/api/admin/clients/${detail.id}/trial`, body);
      await onSaved();
    } finally {
      setBusy(false);
    }
  }

  const enabled = detail.client_status !== "disabled";

  return (
    <div className="space-y-4">
      <div className="card">
        <h3 className="font-semibold text-slate-800">Client status</h3>
        <p className="mb-3 text-sm text-slate-500">
          Determines whether this client receives texts from our AI bots about
          the links they’re sending.
        </p>
        <div className="flex items-center gap-3">
          <span className={`badge ${enabled ? "bg-green-100 text-green-700" : "bg-slate-200 text-slate-500"}`}>
            {enabled ? "Enabled" : "Disabled"}
          </span>
          <button
            className={enabled ? "btn bg-red-600 text-white hover:bg-red-700" : "btn-primary"}
            disabled={busy}
            onClick={() => setStatus(enabled ? "disabled" : "enabled")}
          >
            {enabled ? "Disable client" : "Enable client"}
          </button>
        </div>
      </div>

      <div className="card">
        <h3 className="font-semibold text-slate-800">Trial</h3>
        <p className="mb-3 text-sm text-slate-500">
          {detail.trial_active
            ? `On trial — ${detail.trial_days_left ?? "—"} days left${
                detail.trial_end
                  ? ` (ends ${new Date(detail.trial_end).toLocaleDateString()})`
                  : ""
              }.`
            : "Trial is off. Once a trial is up, disable it and follow up about paid plans."}
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Days left">
            <input
              className="input max-w-[120px]"
              type="number"
              min={0}
              value={days}
              onChange={(e) => setDays(e.target.value)}
            />
          </Field>
          <button className="btn-ghost" disabled={busy} onClick={() => setTrial({ days_left: Number(days || 0) })}>
            Set days left
          </button>
          {detail.trial_active ? (
            <button className="btn bg-slate-800 text-white hover:bg-slate-700" disabled={busy} onClick={() => setTrial({ trial_active: false })}>
              End trial (follow up about plans)
            </button>
          ) : (
            <button className="btn-ghost" disabled={busy} onClick={() => setTrial({ trial_active: true })}>
              Reactivate trial
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function ClaimTab({
  detail,
  me,
  onSaved,
}: {
  detail: ClientDetail;
  me: string;
  onSaved: () => Promise<void>;
}) {
  const [name, setName] = useState(detail.claimed_by ?? "");
  const [busy, setBusy] = useState(false);

  async function save(value: string | null) {
    setBusy(true);
    try {
      await patchClient(detail.id, { claimed_by: value });
      setName(value ?? "");
      await onSaved();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card space-y-4">
      <div>
        <h3 className="font-semibold text-slate-800">Claim</h3>
        <p className="text-sm text-slate-500">
          Mark who has claimed this client so other teammates know not to contact
          them.
        </p>
      </div>
      {detail.claimed_by ? (
        <div className="flex items-center gap-2 rounded-lg bg-indigo-50 px-3 py-2 text-sm text-indigo-700">
          🔒 Claimed by <strong>{detail.claimed_by}</strong>
        </div>
      ) : (
        <div className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-500">
          Unclaimed — anyone can contact this client.
        </div>
      )}
      <Field label="Claimed by">
        <input className="input" placeholder="teammate name" value={name} onChange={(e) => setName(e.target.value)} />
      </Field>
      <div className="flex flex-wrap gap-2">
        <button className="btn-primary" disabled={busy} onClick={() => save(name.trim() || null)}>
          Save
        </button>
        <button className="btn-ghost" disabled={busy} onClick={() => save(me)}>
          Claim for me
        </button>
        {detail.claimed_by && (
          <button className="btn-ghost" disabled={busy} onClick={() => save(null)}>
            Unclaim
          </button>
        )}
      </div>
    </div>
  );
}

function ContactsTab({
  detail,
  onSaved,
}: {
  detail: ClientDetail;
  onSaved: () => Promise<void>;
}) {
  const [c, setC] = useState({ name: "", phone: "", email: "" });
  const [busy, setBusy] = useState(false);

  async function add() {
    if (!c.name && !c.phone && !c.email) return;
    setBusy(true);
    try {
      await api.post(`/api/admin/clients/${detail.id}/contacts`, c);
      setC({ name: "", phone: "", email: "" });
      await onSaved();
    } finally {
      setBusy(false);
    }
  }
  async function remove(id: number) {
    setBusy(true);
    try {
      await api.del(`/api/admin/clients/${detail.id}/contacts/${id}`);
      await onSaved();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="card">
        <h3 className="mb-1 font-semibold text-slate-800">Ways to reach them</h3>
        <p className="mb-3 text-sm text-slate-500">
          Numbers, email, and a good name to use — add as many as you need.
        </p>
        {detail.contacts.length === 0 ? (
          <p className="text-sm text-slate-400">No contacts yet.</p>
        ) : (
          <div className="space-y-2">
            {detail.contacts.map((ct) => (
              <div key={ct.id} className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 px-3 py-2 text-sm">
                <div>
                  <span className="font-medium text-slate-800">{ct.name || "—"}</span>
                  <span className="text-slate-500">
                    {ct.phone ? ` · ${ct.phone}` : ""}
                    {ct.email ? ` · ${ct.email}` : ""}
                  </span>
                </div>
                <button className="btn-ghost px-2 py-1 text-xs" disabled={busy} onClick={() => remove(ct.id)}>
                  Remove
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="card">
        <h3 className="mb-3 font-semibold text-slate-800">Add a contact</h3>
        <div className="grid gap-3 sm:grid-cols-3">
          <input className="input" placeholder="Name" value={c.name} onChange={(e) => setC({ ...c, name: e.target.value })} />
          <input className="input" placeholder="Phone" value={c.phone} onChange={(e) => setC({ ...c, phone: e.target.value })} />
          <input className="input" placeholder="Email" value={c.email} onChange={(e) => setC({ ...c, email: e.target.value })} />
        </div>
        <button className="btn-primary mt-3" disabled={busy} onClick={add}>
          Add contact
        </button>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="label">{label}</label>
      {children}
    </div>
  );
}
