"use client";

import { useState } from "react";
import Link from "next/link";

export function MarketingNav({ dark = false }: { dark?: boolean }) {
  const [open, setOpen] = useState(false);
  const text = dark ? "text-white/80" : "text-slate-600";
  const logo = dark ? "text-white" : "text-brand-700";
  return (
    <header
      className={`sticky top-0 z-30 ${
        dark
          ? "border-b border-white/10 bg-[#070b1a]/80 backdrop-blur"
          : "border-b border-slate-200 bg-white/80 backdrop-blur"
      }`}
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3.5">
        <Link href="/" className={`text-xl font-extrabold tracking-tight ${logo}`}>
          Lead<span className="text-fuchsia-500">Pilot</span>
        </Link>
        <nav className={`hidden items-center gap-7 text-sm font-medium md:flex ${text}`}>
          <Link href="/#how" className="hover:opacity-100 hover:underline">
            How it works
          </Link>
          <Link href="/#features" className="hover:underline">
            Features
          </Link>
          <Link href="/#pricing" className="hover:underline">
            Pricing
          </Link>
          <Link href="/login" className="hover:underline">
            Log in
          </Link>
          <Link href="/start" className="btn-cta-dark !px-5 !py-2.5 !text-sm">
            Start free
          </Link>
        </nav>
        <button
          className={`md:hidden ${dark ? "text-white" : "text-slate-700"}`}
          onClick={() => setOpen(!open)}
          aria-label="Menu"
        >
          ☰
        </button>
      </div>
      {open && (
        <div
          className={`md:hidden ${
            dark ? "bg-[#070b1a] text-white" : "bg-white"
          } border-t ${dark ? "border-white/10" : "border-slate-200"} px-4 py-3`}
        >
          <div className="flex flex-col gap-3 text-sm">
            <Link href="/#how">How it works</Link>
            <Link href="/#features">Features</Link>
            <Link href="/#pricing">Pricing</Link>
            <Link href="/login">Log in</Link>
            <Link href="/start" className="btn-cta-dark !py-2.5 !text-sm">
              Start free
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}

export function MarketingFooter() {
  return (
    <footer className="border-t border-white/10 bg-[#070b1a] text-slate-400">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 py-10 sm:flex-row">
        <div>
          <span className="text-lg font-extrabold tracking-tight text-white">
            Lead<span className="text-fuchsia-500">Pilot</span>
          </span>
          <p className="mt-1 text-sm">AI lead generation for local service pros.</p>
        </div>
        <div className="flex items-center gap-6 text-sm">
          <Link href="/terms" className="hover:text-white">
            Terms
          </Link>
          <Link href="/privacy" className="hover:text-white">
            Privacy
          </Link>
          <Link href="/login" className="hover:text-white">
            Log in
          </Link>
          <Link href="/start" className="font-semibold text-white hover:underline">
            Start free →
          </Link>
        </div>
      </div>
    </footer>
  );
}
