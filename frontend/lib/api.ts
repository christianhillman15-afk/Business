"use client";

import { DEMO, demoRequest } from "./demo";

const BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const TOKEN_KEY = "leadpilot_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  window.localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  // Static demo build: serve everything from the in-browser store, no network.
  if (DEMO) return demoRequest<T>(path, options);

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(p: string) => request<T>(p),
  post: <T>(p: string, body?: unknown) =>
    request<T>(p, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  put: <T>(p: string, body?: unknown) =>
    request<T>(p, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(p: string, body?: unknown) =>
    request<T>(p, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  del: <T>(p: string) => request<T>(p, { method: "DELETE" }),
};

// --- Types (mirror backend schemas) ----------------------------------------
export interface User {
  id: number;
  email: string;
  role: "provider" | "admin";
  business_name: string | null;
  contact_name: string | null;
  phone: string | null;
  nextdoor_handle: string | null;
  onboarding_source: string;
  timezone: string;
  automation_enabled: boolean;
  sms_enabled: boolean;
}

export interface AgentResponse {
  id: number;
  generated_text: string;
  status: "draft" | "approved" | "posted" | "rejected";
  posted_at: string | null;
}

export interface Lead {
  id: number;
  provider: "facebook" | "nextdoor";
  post_url: string | null;
  author: string | null;
  content: string;
  location: string | null;
  status: string;
  relevance_score: number | null;
  relevance_reason: string | null;
  created_at: string;
  response: AgentResponse | null;
}

export interface Quota {
  plan_code: string;
  daily_quota: number;
  used_today: number;
  remaining_today: number;
  on_trial: boolean;
}

export interface Plan {
  code: string;
  name: string;
  price_monthly: number;
  daily_post_quota: number;
}

export interface PricingProfile {
  trade: string | null;
  service_categories: string[];
  price_list: string;
  phone: string | null;
  target_neighborhoods: string[];
}

export type AuthMethod = "oauth" | "managed_business_page" | "session";

export interface ConnectedAccount {
  id: number;
  provider: "facebook" | "nextdoor";
  auth_method: AuthMethod;
  display_name: string | null;
  health: string;
  connected_at: string;
}

export interface Subscription {
  plan_code: string;
  status: string;
  trial_end: string | null;
}

export interface ProviderCapability {
  reply_autopost: boolean;
  broadcast: boolean;
}
export type Capabilities = Record<string, ProviderCapability>;

export interface Broadcast {
  id: number;
  provider: "facebook" | "nextdoor";
  body_text: string;
  status: "draft" | "scheduled" | "posted" | "failed";
  scheduled_for: string | null;
  posted_at: string | null;
  created_at: string;
}

export interface Notification {
  id: number;
  kind: string;
  title: string;
  body: string;
  read: boolean;
  created_at: string;
}
