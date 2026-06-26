"use client";

import { useRouter } from "next/navigation";
import { DEMO } from "@/lib/demo";
import { setToken } from "@/lib/api";

// Thin strip shown only in the static demo build. Gives anyone who opens the
// shared link a one-click way into the product without typing credentials.
export function DemoBanner() {
  const router = useRouter();
  if (!DEMO) return null;

  function openDashboard() {
    setToken("demo-token");
    router.push("/dashboard");
  }

  return (
    <div className="relative z-50 flex flex-wrap items-center justify-center gap-x-3 gap-y-1 bg-slate-900 px-4 py-2 text-center text-xs text-slate-300">
      <span>
        🚀 <strong className="text-white">Live demo</strong> — sample data, no
        sign-up needed.
      </span>
      <button
        onClick={openDashboard}
        className="rounded-full bg-white px-3 py-0.5 text-[11px] font-semibold text-slate-900 hover:bg-slate-100"
      >
        Open the dashboard →
      </button>
    </div>
  );
}
