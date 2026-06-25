"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, Plan, setToken } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [businessName, setBusinessName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [planCode, setPlanCode] = useState("growth");
  const [plans, setPlans] = useState<Plan[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get<Plan[]>("/api/plans").then(setPlans).catch(() => {});
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<{ access_token: string }>("/api/auth/register", {
        email,
        password,
        business_name: businessName,
        plan_code: planCode,
      });
      setToken(res.access_token);
      router.replace("/onboarding");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <h1 className="mb-1 text-center text-2xl font-bold text-brand-700">
          Start your 7-day trial
        </h1>
        <p className="mb-6 text-center text-sm text-slate-500">
          AI-driven local leads for your service business
        </p>
        <form onSubmit={submit} className="card space-y-4">
          <div>
            <label className="label">Business name</label>
            <input
              className="input"
              value={businessName}
              onChange={(e) => setBusinessName(e.target.value)}
              placeholder="Rivertown Plumbing Co."
            />
          </div>
          <div>
            <label className="label">Email</label>
            <input
              className="input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="label">Password</label>
            <input
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              required
            />
            <p className="mt-1 text-xs text-slate-400">At least 8 characters.</p>
          </div>
          <div>
            <label className="label">Plan</label>
            <select
              className="input"
              value={planCode}
              onChange={(e) => setPlanCode(e.target.value)}
            >
              {plans.map((p) => (
                <option key={p.code} value={p.code}>
                  {p.name} — ${p.price_monthly}/mo · {p.daily_post_quota} posts/day
                </option>
              ))}
            </select>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button className="btn-primary w-full" disabled={busy}>
            {busy ? "Creating account…" : "Create account"}
          </button>
          <p className="text-center text-sm text-slate-500">
            Already have an account?{" "}
            <Link href="/login" className="text-brand-600 hover:underline">
              Sign in
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
