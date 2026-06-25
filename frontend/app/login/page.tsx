"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, setToken } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("demo@leadpilot.io");
  const [password, setPassword] = useState("demo1234");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [magicSent, setMagicSent] = useState(false);

  async function sendMagicLink() {
    setError(null);
    if (!email) {
      setError("Enter your email first.");
      return;
    }
    setBusy(true);
    try {
      await api.post("/api/auth/magic/request", { email });
      setMagicSent(true);
    } catch {
      setMagicSent(true); // never reveal whether the email exists
    } finally {
      setBusy(false);
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<{ access_token: string }>("/api/auth/login", {
        email,
        password,
      });
      setToken(res.access_token);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <h1 className="mb-1 text-center text-2xl font-bold text-brand-700">
          LeadPilot
        </h1>
        <p className="mb-6 text-center text-sm text-slate-500">
          Sign in to your dashboard
        </p>
        <form onSubmit={submit} className="card space-y-4">
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
              required
            />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          {magicSent && (
            <p className="rounded-md bg-green-50 p-2 text-center text-sm text-green-700">
              If that email is registered, a one-click sign-in link is on its way.
            </p>
          )}
          <button className="btn-primary w-full" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
          <button
            type="button"
            className="btn-ghost w-full"
            disabled={busy}
            onClick={sendMagicLink}
          >
            Email me a sign-in link (no password)
          </button>
          <p className="text-center text-sm text-slate-500">
            New here?{" "}
            <Link href="/start" className="text-brand-600 hover:underline">
              Start a free trial
            </Link>
          </p>
        </form>
        <p className="mt-4 text-center text-xs text-slate-400">
          Demo: demo@leadpilot.io / demo1234
        </p>
      </div>
    </div>
  );
}
