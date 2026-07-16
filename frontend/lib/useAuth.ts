"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, clearToken, getToken, User } from "./api";

export function useAuth(opts: { redirect?: boolean } = { redirect: true }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) {
      setLoading(false);
      if (opts.redirect) router.replace("/login");
      return;
    }
    api
      .get<User>("/api/auth/me")
      .then(setUser)
      .catch(() => {
        clearToken();
        if (opts.redirect) router.replace("/login");
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function logout() {
    clearToken();
    router.replace("/login");
  }

  return { user, loading, logout, setUser };
}
