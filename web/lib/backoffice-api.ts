// Back-office client (English only). Credentials live in sessionStorage for the tab only.
import { API_URL } from "@/lib/api";

export type Lead = {
  id: string; name: string; segment: string | null; stage: string; reason: string; route: string; partner_code: string | null; territory_team: string;
  city: string | null; score: number | null; score_reasons: string[]; expected_value_paise: number; expected_value_display: string; compliance_hold: string | null; next_action: { code: string; text: string } | null; age_hours: number; status: string; order_id: string | null; quote_id: string | null;
};
export type LeadDetail = Lead & {
  profile: Record<string, unknown>; phone_masked: string | null; preferred_time: string | null;
  quote: { bundle: string; monthly_total_display: string; one_time_total_display: string; lines: { name: string; qty: number; monthly: string }[]; assumptions: string[]; assisted: boolean } | null;
  order: { state: string; business_name: string | null } | null;
  engagement: Record<string, number | boolean> | null;
  kyc: { decision: { status: string; message: string; reason_codes: string[] } | null; issues: { code: string; status: string; label: string; message: string; fix: string | null }[] } | null;
};
export type Funnel = {
  stages: { key: string; label: string; count: number; pct_of_prev: number | null }[];
  kpis: { lead_to_activation_pct: number | null; needs_to_quote_pct: number | null; median_days_to_activate: number | null; activated_orders: number; kyc_auto_approval_pct: number | null; kyc_decisions: number; status_checks_per_order: number | null; orders: number; handoffs: number };
  baseline: Record<string, number>; target: Record<string, number>; seeded_events: number; total_events: number;
};

const KEY = "bo:auth";
export const getAuth = () => {
  try {
    return sessionStorage.getItem(KEY);
  } catch {
    return null;
  }
};
export const setAuth = (user: string, pass: string) => {
  const v = btoa(`${user}:${pass}`);
  try {
    sessionStorage.setItem(KEY, v);
  } catch {
    /* storage blocked: stays in memory only */
  }
  return v;
};
export const clearAuth = () => {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
};

export class AuthError extends Error {}

async function call<T>(auth: string, path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { ...init, headers: { "Content-Type": "application/json", Authorization: `Basic ${auth}`, ...(init?.headers ?? {}) } });
  if (res.status === 401) throw new AuthError("unauthorized");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

export const me = (a: string) => call<{ user: string }>(a, "/backoffice/me");
export const listLeads = (a: string, f: Record<string, string>) =>
  call<{ leads: Lead[] }>(a, `/backoffice/leads?${new URLSearchParams(Object.entries(f).filter(([, v]) => v)).toString()}`).then((r) => r.leads);
export const leadDetail = (a: string, id: string) => call<LeadDetail>(a, `/backoffice/leads/${id}`);
export const setLeadStatus = (a: string, id: string, status: string) => call<Lead>(a, `/backoffice/leads/${id}/status`, { method: "POST", body: JSON.stringify({ status }) });
export const getFunnel = (a: string) => call<Funnel>(a, "/backoffice/funnel");
export const resetDemo = (token: string) =>
  fetch(`${API_URL}/admin/reset`, { method: "POST", headers: { "X-Admin-Token": token } }).then((r) => r.json());
