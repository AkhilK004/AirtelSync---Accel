// Typed client. Types mirror api/app (Pydantic). The frontend never computes money: it only shows *_display strings.
export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    public params: Record<string, unknown> = {},
    message = "",
  ) {
    super(message || code);
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "NETWORK");
  }
  if (!res.ok) {
    let code = "GENERIC";
    let params: Record<string, unknown> = {};
    let message = "";
    try {
      const body = await res.json();
      if (body?.error) {
        code = body.error.code ?? code;
        params = body.error.params ?? {};
        message = body.error.message ?? "";
      } else if (res.status === 422) code = "VALIDATION";
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(res.status, code, params, message);
  }
  return res.json() as Promise<T>;
}

const post = <T>(path: string, body?: unknown, headers?: Record<string, string>) =>
  req<T>(path, { method: "POST", body: JSON.stringify(body ?? {}), headers });

// ---- advisor
export type QuickReply = { label: string; value: string };
export type RecLine = { sku: string; name: string; qty: number; reason: string; line_monthly_display: string };
export type RecSummary = {
  bundle_name: string;
  segment: string;
  lines: RecLine[];
  addon_names: string[];
  monthly_total_display: string;
  monthly_total_paise: number;
  one_time_total_display: string;
  contract_months: number;
  assisted: boolean;
  skipped: string[];
};
export type AdvisorReply = {
  session_id: string;
  message: string;
  quick_replies: QuickReply[];
  progress: { asked: number; total: number };
  action: "ASK" | "CLARIFY" | "RECOMMEND" | "EXPLAIN" | "HANDOFF";
  language: string;
  recommendation: RecSummary | null;
  quote_id: string | null;
  handoff: boolean;
  lead_id: string | null;
  assumption_texts: string[];
};
export const startAdvisor = (language: string, partner_code?: string | null) =>
  post<AdvisorReply>("/advisor/sessions", { language, channel: "web", partner_code: partner_code ?? undefined });
export const sendAdvisor = (sid: string, text: string) => post<AdvisorReply>(`/advisor/sessions/${sid}/messages`, { text });
export const requestCallback = (sid: string, phone: string, preferred_time: string) =>
  post<{ lead_id: string; callback_hours: number }>(`/advisor/sessions/${sid}/handoff`, { phone, preferred_time });

// ---- quote
export type Note = { key: string; params: Record<string, unknown>; text: string };
export type QuoteLine = {
  sku: string; name: string; category: string; description: string; unit: string; need: string; qty: number; required: boolean;
  reason: string; unit_price_display: string; line_monthly_display: string; setup_display: string; setup_paise: number; contract_months: number;
};
export type AddonOption = {
  sku: string; name: string; need: string; qty: number; on: boolean; monthly_display: string; setup_display: string; reason: string;
  can_toggle: boolean;
};
export type Quote = {
  id: string; segment: string; bundle_title: string; lines: QuoteLine[]; addons: AddonOption[];
  monthly_subtotal_display: string; gst_display: string; monthly_total_display: string; monthly_total_paise: number;
  one_time_paise: number; one_time_display: string; one_time_gst_display: string; one_time_total_display: string;
  contract_months: number; gst_rate_pct: number; assumptions: Note[]; assisted: boolean;
};
export const getQuote = (id: string, lang: string) => req<Quote>(`/quotes/${id}?lang=${lang}`);
export const toggleAddon = (id: string, sku: string, on: boolean, lang: string) =>
  post<{ quote: Quote; notices: Note[] }>(`/quotes/${id}/toggle?lang=${lang}`, { sku, on });

// ---- checkout
export const getMeta = () => req<{ today: string; max_slot_days: number }>("/meta");
export const sendOtp = (phone: string) => post<{ sent: boolean }>("/checkout/otp", { phone });
export type CheckoutInput = {
  quote_id: string; phone: string; otp: string; business_name: string; address: string; pincode?: string;
  slot_date: string; slot_window: string; payment_mode: string; language: string;
};
export const placeOrder = (b: CheckoutInput) => post<{ order_id: string; state: string }>("/checkout", b);

// ---- consent + KYC
export type Purpose = { id: string; required: boolean; default: boolean; label: string };
export type Notice = {
  version: string; language: string; title: string; summary: string[]; full: string; purposes: Purpose[];
};
export const getNotice = (lang: string, partner = false) => req<Notice>(`/consents/notice?lang=${lang}&partner=${partner}`);
export const grantConsent = (order_id: string, purposes: string[], language: string) =>
  post<{ id: string; notice_version: string }>("/consents", { order_id, purposes, language, channel: "web" });
export const getConsents = (order_id: string) => req<{ effective: string[] }>(`/consents/${order_id}`);

export type CheckView = { code: string; status: "PASS" | "WARN" | "FAIL"; label: string; message: string; fix: string | null; slot: string | null };
export type KycView = {
  order_id: string; path: string; required: string[]; uploaded: string[]; declared_gstin: string | null; declared_udyam: string | null;
  checks: CheckView[];
  decision: { status: "APPROVED" | "MANUAL_REVIEW" | "ACTION_REQUIRED" | "REJECTED"; message: string; reason_codes: string[]; review_hours: number | null } | null;
};
export type LookupResult = {
  checks: CheckView[];
  record: { legal_name?: string; trade_name?: string; address?: string; state?: string; status?: string; enterprise_name?: string; enterprise_type?: string; city?: string } | null;
};
export const getKyc = (id: string, lang: string) => req<KycView>(`/kyc/${id}?lang=${lang}`);
export const setKycPath = (id: string, path: string, lang: string) => req(`/kyc/${id}/path?lang=${lang}`, { method: "PUT", body: JSON.stringify({ path }) });
export const lookupGstin = (id: string, gstin: string, lang: string) => post<LookupResult>(`/kyc/${id}/lookup/gstin?lang=${lang}`, { gstin });
export const lookupUdyam = (id: string, udyam_number: string, lang: string) => post<LookupResult>(`/kyc/${id}/lookup/udyam?lang=${lang}`, { udyam_number });
export type UploadResult = { slot: string; checks: CheckView[]; summary: Record<string, string>; ok: boolean };
export async function uploadDoc(id: string, slot: string, file: File, lang: string): Promise<UploadResult> {
  const fd = new FormData();
  fd.append("slot", slot);
  fd.append("file", file);
  let res: Response;
  try {
    res = await fetch(`${API_URL}/kyc/${id}/documents?lang=${lang}`, { method: "POST", body: fd }); // the browser sets the multipart boundary
  } catch {
    throw new ApiError(0, "NETWORK");
  }
  if (!res.ok) {
    const b = await res.json().catch(() => null);
    throw new ApiError(res.status, b?.error?.code ?? "GENERIC", b?.error?.params ?? {});
  }
  return res.json();
}
export const evaluateKyc = (id: string, lang: string) => post<KycView>(`/kyc/${id}/evaluate?lang=${lang}`);

// ---- orders / tracker
export type TrackStep = { key: string; label: string; status: "done" | "current" | "upcoming"; eta: string | null };
export type TrackLine = { sku: string; name: string; qty: number; mode: "digital" | "physical"; status: string; status_label: string; eta: string | null; install_days: number };
export type OrderView = {
  id: string; state: string; state_label: string; side_state: string | null; side_message: string | null; business_name: string | null;
  slot: { date: string; window: string; window_label: string }; tech: string | null; steps: TrackStep[]; lines: TrackLine[]; eta_activation: string | null;
  events: { ts: string; state: string; text: string }[]; messages: { ts: string; channel: "whatsapp" | "sms"; text: string }[];
  monthly_total_display: string; one_time_total_display: string; can_reschedule: boolean; needs_kyc: boolean; callback_hours: number;
};
export const getOrder = (id: string, last4: string, lang: string, track = false) => req<OrderView>(`/orders/${id}?phone_last4=${last4}&lang=${lang}&track=${track}`);
export const rescheduleOrder = (id: string, last4: string, slot_date: string, slot_window: string, lang: string) =>
  post<OrderView>(`/orders/${id}/reschedule?lang=${lang}`, { phone_last4: last4, slot_date, slot_window });
export const orderCallback = (id: string, last4: string) => post<{ lead_id: string }>(`/orders/${id}/callback`, { phone_last4: last4 });
export const demoAdvance = (id: string, token: string, lang: string) =>
  post<OrderView>(`/admin/orders/${id}/advance?lang=${lang}`, undefined, { "X-Admin-Token": token });
