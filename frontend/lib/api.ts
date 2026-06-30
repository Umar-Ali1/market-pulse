/**
 * API client — wraps fetch with auth header injection and error handling.
 *
 * Token management:
 *   Access token stored in memory (not localStorage — XSS risk).
 *   Refresh token stored in an httpOnly cookie (set by Django).
 *   On 401, attempt silent refresh before failing.
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

let accessToken: string | null = null;

export function setAccessToken(token: string) {
  accessToken = token;
}

export function clearAccessToken() {
  accessToken = null;
}

// ── Types ──────────────────────────────────────────────────────

export interface Candle {
  ts_bucket: string;
  open:      number;
  high:      number;
  low:       number;
  close:     number;
  volume:    number;
}

export interface CandleResponse {
  asset:    string;
  interval: string;
  candles:  Candle[];
  source:   "cache" | "db";
}

export interface Asset {
  asset:        string;
  price:        number;
  last_updated: string;
}

export type Interval = "1m" | "5m" | "1h" | "1d";

// ── Fetch wrapper ──────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  const res = await fetch(url, { ...options, headers });

  if (res.status === 401) {
    // Attempt token refresh
    const refreshed = await tryRefresh();
    if (refreshed) {
      headers["Authorization"] = `Bearer ${accessToken}`;
      const retry = await fetch(url, { ...options, headers });
      if (!retry.ok) throw new ApiError(retry.status, await retry.text());
      return retry.json();
    }
    throw new ApiError(401, "Session expired");
  }

  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(res.status, body);
  }

  return res.json();
}

async function tryRefresh(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/api/v1/auth/token/refresh/`, {
      method: "POST",
      credentials: "include",   // sends httpOnly refresh token cookie
      headers: { "Content-Type": "application/json" },
    });
    if (!res.ok) return false;
    const data = await res.json();
    accessToken = data.access;
    return true;
  } catch {
    return false;
  }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

// ── Endpoint functions ─────────────────────────────────────────

export async function fetchCandles(
  asset: string,
  interval: Interval,
  from: string,
  to: string,
): Promise<CandleResponse> {
  const params = new URLSearchParams({ asset, interval, from, to });
  return apiFetch<CandleResponse>(`/api/v1/candles/?${params}`);
}

export async function fetchAssets(): Promise<{ assets: Asset[] }> {
  return apiFetch<{ assets: Asset[] }>("/api/v1/assets/");
}

export async function login(
  username: string,
  password: string,
): Promise<void> {
  const data = await apiFetch<{ access: string }>("/api/v1/auth/token/", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  setAccessToken(data.access);
}
