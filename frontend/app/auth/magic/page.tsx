"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api, setToken } from "@/lib/api";

function MagicInner() {
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      setError("This link is missing its token.");
      return;
    }
    api
      .post<{ access_token: string }>("/api/auth/magic/verify", { token })
      .then((res) => {
        setToken(res.access_token);
        router.replace("/dashboard");
      })
      .catch(() => setError("This sign-in link is invalid or has expired."));
  }, [params, router]);

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="card max-w-sm text-center">
        {error ? (
          <>
            <h1 className="mb-1 text-xl font-bold">Sign-in failed</h1>
            <p className="mb-4 text-sm text-slate-500">{error}</p>
            <Link href="/login" className="btn-primary">
              Back to sign in
            </Link>
          </>
        ) : (
          <p className="text-slate-400">Signing you in…</p>
        )}
      </div>
    </div>
  );
}

export default function MagicPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center text-slate-400">
          Loading…
        </div>
      }
    >
      <MagicInner />
    </Suspense>
  );
}
