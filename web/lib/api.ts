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

const post = <T>(path: string, body?: unknown) => req<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) });

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
