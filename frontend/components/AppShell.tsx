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
  { href: "/free-trial", label: "Free Trial" },
  { href: "/support", label: "Support" },
  { href: "/settings", label: "Settings" },
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
  const [menuOpen, setMenuOpen] = useState(false);
  const nav = [...NAV];
  if (user.role === "admin") nav.push({ href: "/admin", label: "Admin" });

  useEffect(() => {
    api
      .get<{ unread: number }>("/api/notifications/unread-count")
      .then((r) => setUnread(r.unread))
      .catch(() => {});
  }, [pathname]);

  // Close the mobile menu whenever the route changes.
  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  const isActive = (href: string) =>
    pathname === href || pathname.startsWith(href + "/");

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-center gap-6">
            <Link href="/dashboard" className="text-lg font-extrabold tracking-tight">
              <span className="text-grad-dark">Lead</span>
              <span className="text-slate-900">Pilot</span>
            </Link>
            <nav className="hidden gap-1 md:flex">
              {nav.map((item) => {
                const active = isActive(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                      active
                        ? "bg-gradient-to-r from-indigo-50 to-fuchsia-50 text-indigo-700 ring-1 ring-inset ring-indigo-100"
                        : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            <Link
              href="/notifications"
              className="relative rounded-lg px-2 py-1.5 text-slate-500 hover:bg-slate-100"
              title="Notifications"
            >
              <span aria-hidden>🔔</span>
              {unread > 0 && (
                <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
                  {unread > 9 ? "9+" : unread}
                </span>
              )}
            </Link>
            <span className="hidden text-sm text-slate-500 lg:inline">
              {user.business_name || user.email}
            </span>
            <button className="btn-ghost hidden md:inline-flex" onClick={onLogout}>
              Log out
            </button>

            {/* Mobile menu toggle */}
            <button
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-100 md:hidden"
              aria-label={menuOpen ? "Close menu" : "Open menu"}
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((o) => !o)}
            >
              <span aria-hidden className="text-lg leading-none">
                {menuOpen ? "✕" : "☰"}
              </span>
            </button>
          </div>
        </div>

        {/* Mobile nav panel */}
        {menuOpen && (
          <div className="border-t border-slate-200 bg-white md:hidden">
            <nav className="mx-auto grid max-w-6xl gap-1 px-3 py-3">
              {nav.map((item) => {
                const active = isActive(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`rounded-lg px-3 py-2.5 text-sm font-medium ${
                      active
                        ? "bg-gradient-to-r from-indigo-50 to-fuchsia-50 text-indigo-700 ring-1 ring-inset ring-indigo-100"
                        : "text-slate-700 hover:bg-slate-100"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
              <button
                className="mt-1 rounded-lg px-3 py-2.5 text-left text-sm font-medium text-slate-700 hover:bg-slate-100"
                onClick={onLogout}
              >
                Log out
              </button>
            </nav>
          </div>
        )}
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
    </div>
  );
}
