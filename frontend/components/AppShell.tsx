"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { api, User } from "@/lib/api";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/broadcast", label: "Business Posts" },
  { href: "/onboarding", label: "Setup" },
  { href: "/billing", label: "Billing" },
  { href: "/support", label: "Support" },
];

export function AppShell({
  user,
  onLogout,
  children,
}: {
  user: User;
  onLogout: () => void;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const [unread, setUnread] = useState(0);
  const nav = [...NAV];
  if (user.role === "admin") nav.push({ href: "/admin", label: "Admin" });

  useEffect(() => {
    api
      .get<{ unread: number }>("/api/notifications/unread-count")
      .then((r) => setUnread(r.unread))
      .catch(() => {});
  }, [pathname]);

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-8">
            <Link href="/dashboard" className="text-lg font-bold text-brand-700">
              LeadPilot
            </Link>
            <nav className="hidden gap-1 sm:flex">
              {nav.map((item) => {
                const active = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                      active
                        ? "bg-brand-50 text-brand-700"
                        : "text-slate-600 hover:bg-slate-100"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/notifications"
              className="relative rounded-md px-2 py-1.5 text-slate-500 hover:bg-slate-100"
              title="Notifications"
            >
              <span aria-hidden>🔔</span>
              {unread > 0 && (
                <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
                  {unread > 9 ? "9+" : unread}
                </span>
              )}
            </Link>
            <span className="hidden text-sm text-slate-500 sm:inline">
              {user.business_name || user.email}
            </span>
            <button className="btn-ghost" onClick={onLogout}>
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
    </div>
  );
}
