import { Component, type ErrorInfo, type ReactNode, useCallback, useEffect, useState } from "react";
import {
  Activity,
  ArrowRight,
  Ban,
  Check,
  ChevronRight,
  CircleDot,
  Clock3,
  CreditCard,
  ExternalLink,
  FileKey2,
  Fingerprint,
  Gauge,
  ListTree,
  LockKeyhole,
  Play,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Tag,
  TriangleAlert,
  UploadCloud,
  UserCheck,
  X,
} from "lucide-react";

interface ErrorBoundaryProps {
  children: ReactNode;
  onReset?: () => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  public state: ErrorBoundaryState = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("ErrorBoundary caught an unhandled component error:", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="view-error-boundary">
          <ShieldAlert size={36} color="#ef4444" />
          <h3>View Render Exception</h3>
          <p>{this.state.error?.message ?? "An unexpected error occurred while rendering this view."}</p>
          <button
            className="btn-primary"
            onClick={() => {
              this.setState({ hasError: false, error: null });
              this.props.onReset?.();
            }}
          >
            <span>Reset to Control Room</span>
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

type View = "overview" | "catalog" | "issue" | "mandate" | "simulator" | "stepup" | "audit";

type Product = {
  id: string;
  merchant_id: string;
  name: string;
  price_paise: number;
  currency: string;
  category: string;
  condition: string;
  active: boolean;
  attributes: Record<string, unknown>;
};

type Mandate = {
  id: string;
  instruction_text: string;
  hard_constraints: Record<string, unknown>;
  semantic_constraints: { id: string; text: string }[];
  status: string;
  version: number;
  expires_at: string;
  max_executions: number;
  execution_count: number;
  signature: string;
  created_at: string;
  revoked_at: string | null;
};

type HardCheck = {
  name: string;
  passed: boolean;
  expected: unknown;
  actual: unknown;
  source: string;
};

type SemanticResult = {
  constraint_id: string;
  status: string;
  evidence: { field: string; value: unknown; source: string; citation?: string }[];
  reason: string;
  confidence?: number | null;
  abstain?: boolean;
  citation?: string | null;
};

type Decision = {
  decision: "ALLOW" | "BLOCK" | "STEP_UP";
  reason_code: string | null;
  proposal_id: string;
  step_up_id: string | null;
  hard_gate: { status: string; reason_code: string | null; checks: HardCheck[] };
  semantic: { results: SemanticResult[]; service_status: string } | null;
};

type AuditEvent = {
  id: string;
  event_type: string;
  entity_id: string;
  payload: Record<string, unknown>;
  created_at: string;
};

type Draft = {
  instruction_text: string;
  hard_constraints: Record<string, unknown> | null;
  semantic_constraints: { id: string; text: string }[];
  unresolved: { field: string; reason: string }[];
};

type Order = {
  proposal_id: string;
  razorpay_order_id: string;
  status: string;
  idempotent_replay: boolean;
  key_id: string | null;
  amount: number | null;
  currency: string | null;
  product_name: string | null;
};

type PaymentResult = {
  proposal_id: string;
  razorpay_order_id: string;
  razorpay_payment_id: string;
  status: string;
  idempotent_replay: boolean;
};

type RazorpaySuccess = {
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
};

type MerchantMetrics = {
  merchant_id: string;
  total_skus?: number;
  catalog_sku_count?: number;
  active_skus?: number;
  machine_readable_pct?: number | null;
  machine_readability_score?: number | null;
  autonomous_gmv_paise: number;
  prevented_overspend_paise?: number;
  blocked_overspend_paise?: number;
  total_proposals: number;
  executed_proposals?: number;
  allowed_count?: number;
  blocked_proposals?: number;
  blocked_count?: number;
  conversion_rate_pct?: number | null;
  p95_authorization_latency_ms?: number | null;
  p50_authorization_latency_ms?: number | null;
  authorization_success_rate_pct?: number | null;
  step_up_rate_pct?: number | null;
  semantic_rejection_rate_pct?: number | null;
  payment_success_rate_pct?: number | null;
  duplicate_prevention_count?: number;
};

type AgentStep = {
  step_num: number;
  title: string;
  detail: string;
  status: string;
};

type CandidateEvaluation = {
  product_id: string;
  name: string;
  price_paise: number;
  hard_eligible: boolean;
  rejection_reason: string | null;
  semantic_score: number;
  confidence?: number | null;
  citations?: string[];
  evidence_badges?: { field: string; value: unknown; status: string; citation?: string }[];
  abstain?: boolean;
  semantic_notes: string | null;
};

type AutonomousShopResult = {
  mandate_id: string;
  merchant_id: string;
  steps: AgentStep[];
  candidates_evaluated: CandidateEvaluation[];
  selected_product_id: string | null;
  selected_product_name: string | null;
  agent_reasoning: string;
  proposal_id: string | null;
  decision: "ALLOW" | "BLOCK" | "STEP_UP";
  reason_code: string | null;
  razorpay_order_id: string | null;
  status: string;
  key_id: string | null;
  amount_paise: number | null;
  currency: string;
  step_up_id: string | null;
};

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => { open: () => void };
  }
}

const API = import.meta.env.VITE_API_URL ?? "";
let accessTokenProvider: () => Promise<string | null> = async () => null;
const defaultInstruction = "Buy noise-cancelling headphones under ₹20k. Nothing refurbished. Good for travel. Nothing flashy.";

const navItems: { id: View; label: string; icon: typeof Gauge }[] = [
  { id: "overview", label: "Control Room", icon: Gauge },
  { id: "catalog", label: "Merchant Catalog", icon: UploadCloud },
  { id: "issue", label: "Issue Mandate", icon: FileKey2 },
  { id: "mandate", label: "Mandate Envelope", icon: Fingerprint },
  { id: "simulator", label: "Checkout Engine", icon: ShoppingBag },
  { id: "stepup", label: "Human Step-Up", icon: UserCheck },
  { id: "audit", label: "Signal Feed", icon: ListTree },
];

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = await accessTokenProvider();
  const response = await fetch(`${API}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
    ...init,
  });
  const text = await response.text();
  let body: any = {};
  try {
    body = text ? JSON.parse(text) : {};
  } catch {
    body = { detail: { message: text } };
  }
  if (!response.ok) {
    throw new Error(body?.detail?.reason_code ?? body?.detail?.message ?? `HTTP ${response.status}`);
  }
  return body as T;
}

async function loadRazorpayCheckout(): Promise<void> {
  if (window.Razorpay) return;
  await new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("RAZORPAY_CHECKOUT_UNAVAILABLE"));
    document.head.appendChild(script);
  });
}

const money = (paise: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(paise / 100);

const when = (value: string) =>
  new Intl.DateTimeFormat("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    day: "2-digit",
    month: "short",
  }).format(new Date(value));

const pretty = (value: string) => (value || "").replaceAll("_", " ");

function StateBadge({ value }: { value: string }) {
  const tone = ["ALLOW", "PASS", "ACTIVE", "EXECUTED", "SUPPORTED", "PAID", "CREATED", "VERIFIED"].includes(value)
    ? "good"
    : ["BLOCK", "FAIL", "REVOKED", "REJECTED", "CONTRADICTED", "FAILED"].includes(value)
    ? "bad"
    : "warn";
  return (
    <span className={`state-tag ${tone}`}>
      <CircleDot size={10} />
      {pretty(value)}
    </span>
  );
}

export default function App({
  getAccessToken,
  userControl,
}: {
  getAccessToken?: () => Promise<string | null>;
  userControl?: ReactNode;
}) {
  useEffect(() => {
    accessTokenProvider = getAccessToken ?? (async () => null);
    return () => {
      accessTokenProvider = async () => null;
    };
  }, [getAccessToken]);

  const [view, setView] = useState<View>("overview");
  const [products, setProducts] = useState<Product[]>([]);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [mandate, setMandate] = useState<Mandate | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [instruction, setInstruction] = useState(defaultInstruction);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [selected, setSelected] = useState("");
  const [stepUp, setStepUp] = useState<Record<string, unknown> | null>(null);
  const [order, setOrder] = useState<Order | null>(null);
  const [payment, setPayment] = useState<PaymentResult | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [merchantId, setMerchantId] = useState(import.meta.env.VITE_MERCHANT_ID ?? "merchant_demo");
  const [metrics, setMetrics] = useState<MerchantMetrics | null>(null);
  const [buyerResult, setBuyerResult] = useState<AutonomousShopResult | null>(null);

  const refresh = useCallback(async () => {
    try {
      const catalogPath = merchantId
        ? `/api/v1/products?merchant_id=${encodeURIComponent(merchantId)}`
        : "/api/v1/products";
      const metricsPath = merchantId
        ? `/api/v1/products/metrics?merchant_id=${encodeURIComponent(merchantId)}`
        : "/api/v1/products/metrics";
      const [catalogRes, eventsRes, metricsRes] = await Promise.all([
        request<Product[]>(catalogPath).catch(() => []),
        request<AuditEvent[]>("/api/v1/audit?limit=100").catch(() => []),
        request<MerchantMetrics>(metricsPath).catch(() => null),
      ]);
      const catalog = Array.isArray(catalogRes) ? catalogRes : [];
      const events = Array.isArray(eventsRes) ? eventsRes : [];
      if (metricsRes) setMetrics(metricsRes);

      if (catalog.length === 0 && merchantId !== "merchant_demo") {
        const allProducts = await request<Product[]>("/api/v1/products").catch(() => []);
        if (Array.isArray(allProducts) && allProducts.length > 0) {
          setProducts(allProducts);
          if (allProducts[0]?.merchant_id) {
            setMerchantId(allProducts[0].merchant_id);
          }
          setAudit(events);
          return;
        }
      }

      setProducts(catalog);
      setAudit(events);
    } catch (err) {
      console.error("Refresh error:", err);
    }
  }, [merchantId]);

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, [refresh]);

  useEffect(() => {
    if (!merchantId && products[0]?.merchant_id) setMerchantId(products[0].merchant_id);
  }, [merchantId, products]);

  useEffect(() => {
    if (products.length && !products.some((product) => product.id === selected)) {
      setSelected(products[0].id);
    }
  }, [products, selected]);

  async function act(label: string, fn: () => Promise<void>) {
    setBusy(label);
    setError("");
    try {
      await fn();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusy("");
    }
  }

  const compile = () =>
    act("compile", async () => {
      setDraft(
        await request<Draft>("/api/v1/mandates/compile", {
          method: "POST",
          body: JSON.stringify({ instruction_text: instruction, merchant_id: merchantId }),
        }),
      );
    });

  const issue = () =>
    draft?.hard_constraints &&
    act("issue", async () => {
      const value = await request<Mandate>("/api/v1/mandates", {
        method: "POST",
        body: JSON.stringify({
          instruction_text: instruction,
          hard_constraints: draft.hard_constraints,
          semantic_constraints: draft.semantic_constraints,
          expires_at: new Date(Date.now() + 3600000).toISOString(),
        }),
      });
      setMandate(value);
      setDecision(null);
      setOrder(null);
      setPayment(null);
      setView("mandate");
    });

  const revoke = () =>
    mandate &&
    act("revoke", async () => {
      setMandate(await request<Mandate>(`/api/v1/mandates/${mandate.id}/revoke`, { method: "POST" }));
    });

  const propose = () =>
    mandate &&
    act("propose", async () => {
      const value = await request<{ decision: Decision }>("/api/v1/proposals", {
        method: "POST",
        body: JSON.stringify({
          mandate_id: mandate.id,
          mandate_version: mandate.version,
          product_id: selected,
          quantity: 1,
          agent_request_id: `agent-${crypto.randomUUID()}`,
        }),
      });
      setDecision(value.decision);
      setOrder(null);
      setPayment(null);
      if (value.decision.step_up_id) {
        setStepUp(await request(`/api/v1/step-ups/${value.decision.step_up_id}`));
      }
    });

  const execute = () =>
    decision &&
    act("execute", async () => {
      setOrder(await request<Order>(`/api/v1/proposals/${decision.proposal_id}/execute`, { method: "POST" }));
    });

  const resolve = (choice: "approve" | "reject") =>
    decision?.step_up_id &&
    act(choice, async () => {
      if (choice === "approve") {
        const value = await request<Order>(`/api/v1/step-ups/${decision.step_up_id}/approve`, { method: "POST" });
        setOrder(value);
        setStepUp((current) => (current ? { ...current, status: "APPROVED" } : current));
      } else {
        setStepUp(await request<Record<string, unknown>>(`/api/v1/step-ups/${decision.step_up_id}/reject`, { method: "POST" }));
      }
    });

  const dispatchAutonomousShop = (autoExecute: boolean = true) =>
    mandate &&
    act("autonomous-shop", async () => {
      const res = await request<AutonomousShopResult>("/api/v1/proposals/autonomous-shop", {
        method: "POST",
        body: JSON.stringify({
          mandate_id: mandate.id,
          merchant_id: merchantId,
          auto_execute: autoExecute,
        }),
      });
      setBuyerResult(res);
      setDecision({
        decision: res.decision,
        reason_code: res.reason_code,
        proposal_id: res.proposal_id ?? "",
        step_up_id: res.step_up_id,
        hard_gate: { status: res.decision === "BLOCK" ? "FAIL" : "PASS", reason_code: res.reason_code, checks: [] },
        semantic: null,
      });
      if (res.razorpay_order_id) {
        setOrder({
          proposal_id: res.proposal_id ?? "",
          razorpay_order_id: res.razorpay_order_id,
          status: res.status,
          idempotent_replay: false,
          key_id: res.key_id,
          amount: res.amount_paise,
          currency: res.currency,
          product_name: res.selected_product_name,
        });
      } else {
        setOrder(null);
      }
      setPayment(null);
      if (res.step_up_id) {
        setStepUp(await request(`/api/v1/step-ups/${res.step_up_id}`));
      }
    });

  async function checkout() {
    if (!order?.key_id || !order.amount || !order.currency) {
      return setError("RAZORPAY_CHECKOUT_CONFIGURATION_MISSING");
    }
    setBusy("checkout");
    setError("");
    try {
      await loadRazorpayCheckout();
      if (!window.Razorpay) throw new Error("RAZORPAY_CHECKOUT_UNAVAILABLE");
      const rzpInstance = new window.Razorpay({
        key: order.key_id,
        amount: order.amount,
        currency: order.currency,
        name: "JANUS Authorized Gateway",
        description: order.product_name ?? "Merchant order checkout",
        order_id: order.razorpay_order_id,
        handler: async (result: RazorpaySuccess) => {
          try {
            setBusy("verify");
            const verified = await request<PaymentResult>(
              `/api/v1/proposals/${order.proposal_id}/payments/verify`,
              {
                method: "POST",
                body: JSON.stringify(result),
              },
            );
            setPayment(verified);
            await refresh();
          } catch (err) {
            setError(err instanceof Error ? err.message : "PAYMENT_VERIFICATION_FAILED");
          } finally {
            setBusy("");
          }
        },
        modal: { ondismiss: () => setBusy("") },
        theme: { color: "#6a3df0" },
      });
      rzpInstance.open();
    } catch (err) {
      setError(err instanceof Error ? err.message : "RAZORPAY_CHECKOUT_UNAVAILABLE");
      setBusy("");
    }
  }

  const simulateStepUp = async () => {
    act("simulate-stepup", async () => {
      let currentMandate = mandate;
      if (!currentMandate || currentMandate.status !== "ACTIVE") {
        const draftRes = await request<Draft>("/api/v1/mandates/compile", {
          method: "POST",
          body: JSON.stringify({
            instruction_text: "Buy noise-cancelling headphones under ₹20k. Nothing flashy.",
            merchant_id: merchantId,
          }),
        });
        if (draftRes.hard_constraints) {
          currentMandate = await request<Mandate>("/api/v1/mandates", {
            method: "POST",
            body: JSON.stringify({
              instruction_text: "Buy noise-cancelling headphones under ₹20k. Nothing flashy.",
              hard_constraints: draftRes.hard_constraints,
              semantic_constraints: draftRes.semantic_constraints,
              expires_at: new Date(Date.now() + 3600000).toISOString(),
            }),
          });
          setMandate(currentMandate);
        }
      }
      if (!currentMandate) return;

      const flashy = (Array.isArray(products) ? products : []).find((p) => p.id === "prod_c") || products[0];
      if (!flashy) return;
      setSelected(flashy.id);

      const value = await request<{ decision: Decision }>("/api/v1/proposals", {
        method: "POST",
        body: JSON.stringify({
          mandate_id: currentMandate.id,
          mandate_version: currentMandate.version,
          product_id: flashy.id,
          quantity: 1,
          agent_request_id: `agent-${crypto.randomUUID()}`,
        }),
      });
      setDecision(value.decision);
      setOrder(null);
      setPayment(null);
      if (value.decision.step_up_id) {
        setStepUp(await request(`/api/v1/step-ups/${value.decision.step_up_id}`));
      }
      setView("stepup");
    });
  };

  const simulateAdversarial = async () => {
    act("simulate-adversarial", async () => {
      let currentMandate = mandate;
      if (!currentMandate || currentMandate.status !== "ACTIVE") {
        const draftRes = await request<Draft>("/api/v1/mandates/compile", {
          method: "POST",
          body: JSON.stringify({
            instruction_text: "Buy noise-cancelling headphones under ₹20k. Nothing flashy.",
            merchant_id: merchantId,
          }),
        });
        if (draftRes.hard_constraints) {
          currentMandate = await request<Mandate>("/api/v1/mandates", {
            method: "POST",
            body: JSON.stringify({
              instruction_text: "Buy noise-cancelling headphones under ₹20k. Nothing flashy.",
              hard_constraints: draftRes.hard_constraints,
              semantic_constraints: draftRes.semantic_constraints,
              expires_at: new Date(Date.now() + 3600000).toISOString(),
            }),
          });
          setMandate(currentMandate);
        }
      }
      if (!currentMandate) return;

      const trojan = (Array.isArray(products) ? products : []).find((p) => p.id === "prod_trojan") || products[0];
      if (!trojan) return;
      setSelected(trojan.id);

      const value = await request<{ decision: Decision }>("/api/v1/proposals", {
        method: "POST",
        body: JSON.stringify({
          mandate_id: currentMandate.id,
          mandate_version: currentMandate.version,
          product_id: trojan.id,
          quantity: 1,
          agent_request_id: `agent-${crypto.randomUUID()}`,
        }),
      });
      setDecision(value.decision);
      setOrder(null);
      setPayment(null);
      if (value.decision.step_up_id) {
        setStepUp(await request(`/api/v1/step-ups/${value.decision.step_up_id}`));
      }
      setView("stepup");
    });
  };

  return (
    <div className="window-shell">
      {/* Top Scout-Style Announcement Banner */}
      <div className="announcement-bar">
        <span className="announcement-badge">Live Gateway</span>
        <span>Deterministic Hard Gate · Semantic Intent Path · Razorpay Test-Mode Execution</span>
      </div>

      {/* Main Cockpit Body (100dvh strict fit) */}
      <div className="cockpit-body">
        {/* Left Sidebar Navigation */}
        <aside className="cockpit-sidebar">
          <div className="brand-section">
            <div className="brand-bars">
              <div className="brand-bar" />
              <div className="brand-bar" />
              <div className="brand-bar" />
            </div>
            <span className="brand-title">JANUS</span>
            <span className="brand-tag">v1.0</span>
          </div>

          <nav className="sidebar-nav">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = view === item.id;
              let badgeText = "";
              if (item.id === "catalog") badgeText = String(products.length);
              if (item.id === "audit") badgeText = String(audit.length);
              if (item.id === "stepup" && decision?.decision === "STEP_UP") badgeText = "1";
              if (item.id === "mandate" && mandate?.status === "ACTIVE") badgeText = "active";

              return (
                <button
                  key={item.id}
                  className={`nav-item-btn ${isActive ? "active" : ""}`}
                  onClick={() => setView(item.id)}
                >
                  <Icon size={16} />
                  <span>{item.label}</span>
                  {badgeText && <span className="nav-badge">{badgeText}</span>}
                </button>
              );
            })}
          </nav>

          <div className="sidebar-footer">
            <div className="merchant-pill-box">
              <div className="merchant-dot" />
              <div className="merchant-meta">
                <span className="merchant-label">MERCHANT AUTHORITY</span>
                <span className="merchant-val">{merchantId || "UNBOUND"}</span>
              </div>
            </div>
          </div>
        </aside>

        {/* Main Workspace Area */}
        <main className="cockpit-workspace">
          {/* Topbar */}
          <header className="workspace-topbar">
            <div className="topbar-left">
              <span className="page-title">
                {navItems.find((n) => n.id === view)?.label ?? "Control Room"}
              </span>
              <span className="page-subtitle">
                {view === "overview" && "Autonomous boundary control"}
                {view === "catalog" && "Authoritative merchant products"}
                {view === "issue" && "Intent compilation & signing"}
                {view === "mandate" && "Active cryptographic envelope"}
                {view === "simulator" && "Agent checkout & payment verification"}
                {view === "stepup" && "Human escalation decision"}
                {view === "audit" && "Real-time structured decision log"}
              </span>
            </div>
            <div className="topbar-right">
              <span className="tag-failclosed">
                <ShieldCheck size={12} />
                FAIL-CLOSED
              </span>
              {userControl}
              <a
                className="github-link"
                href="https://github.com/vivekyarra/Janus"
                target="_blank"
                rel="noreferrer"
              >
                <span>Codebase</span>
                <ExternalLink size={12} />
              </a>
            </div>
          </header>

          {/* Global Error Toast */}
          {error && (
            <div className="global-error-toast">
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <TriangleAlert size={15} />
                <span>{error}</span>
              </div>
              <button onClick={() => setError("")} aria-label="Dismiss error">
                <X size={14} />
              </button>
            </div>
          )}

          {/* Inner Content Area */}
          <div className="workspace-content">
            <ErrorBoundary onReset={() => setView("overview")}>
              {view === "overview" && (
                <OverviewView
                  products={products}
                  events={audit}
                  mandate={mandate}
                  metrics={metrics}
                  go={setView}
                  onSelectProductAndGo={(skuId) => {
                    setSelected(skuId);
                    setView("simulator");
                  }}
                />
              )}

              {view === "catalog" && (
                <CatalogView
                  products={products}
                  merchantId={merchantId}
                  setMerchantId={setMerchantId}
                  refresh={refresh}
                  busy={busy}
                  act={act}
                  metrics={metrics}
                />
              )}

              {view === "issue" && (
                <IssueView
                  instruction={instruction}
                  setInstruction={setInstruction}
                  merchantId={merchantId}
                  setMerchantId={setMerchantId}
                  draft={draft}
                  compile={compile}
                  issue={issue}
                  busy={busy}
                />
              )}

              {view === "mandate" && (
                <MandateDetailView
                  mandate={mandate}
                  revoke={revoke}
                  busy={busy}
                  goSimulator={() => setView("simulator")}
                />
              )}

              {view === "simulator" && (
                <SimulatorView
                  mandate={mandate}
                  products={products}
                  selected={selected}
                  setSelected={setSelected}
                  propose={propose}
                  execute={execute}
                  checkout={checkout}
                  payment={payment}
                  decision={decision}
                  order={order}
                  busy={busy}
                  goStepUp={() => setView("stepup")}
                  buyerResult={buyerResult}
                  dispatchAutonomousShop={dispatchAutonomousShop}
                  merchantId={merchantId}
                />
              )}

              {view === "stepup" && (
                <StepUpView
                  decision={decision}
                  data={stepUp}
                  order={order}
                  resolve={resolve}
                  busy={busy}
                  checkout={checkout}
                  payment={payment}
                  onSimulateStepUp={simulateStepUp}
                  onSimulateAdversarial={simulateAdversarial}
                  mandate={mandate}
                />
              )}

              {view === "audit" && (
                <AuditFeedView
                  events={audit}
                  refresh={() => act("refresh", refresh)}
                  busy={busy}
                />
              )}
            </ErrorBoundary>
          </div>
        </main>
      </div>
    </div>
  );
}

/* ==========================================================================
   VIEW 1: CONTROL ROOM (OVERVIEW)
   ========================================================================== */
function OverviewView({
  products,
  events,
  mandate,
  metrics,
  go,
  onSelectProductAndGo,
}: {
  products: Product[];
  events: AuditEvent[];
  mandate: Mandate | null;
  metrics: MerchantMetrics | null;
  go: (v: View) => void;
  onSelectProductAndGo?: (skuId: string) => void;
}) {
  const [activeScenario, setActiveScenario] = useState<"allow" | "hard_block" | "stepup" | "revoked" | "adversarial">("allow");

  const scenarios = [
    {
      id: "allow" as const,
      label: "Demo 1: Autonomous Allow",
      sku: "prod_a",
      name: "Sony Voyager NC (₹18,499)",
      hardGate: "PASS (Amount ≤ ₹20k, Currency INR, Merchant match)",
      semantic: "SUPPORTED (Foldable, travel case, minimal branding)",
      verdict: "ALLOW",
      outcome: "Razorpay Test Order created directly",
      decision: "ALLOW",
      razorpay: "Razorpay Test Order created directly",
      theme: "pass",
    },
    {
      id: "hard_block" as const,
      label: "Demo 2: Hard Gate Violation",
      sku: "prod_b",
      name: "Sony Studio Pro (₹21,499)",
      hardGate: "FAIL: AMOUNT_LIMIT_EXCEEDED (₹21,499 > ₹20,000 ceiling)",
      semantic: "SHORT-CIRCUITED (never invoked on hard fail)",
      verdict: "BLOCK",
      outcome: "Zero money moved · Razorpay call count = 0",
      decision: "BLOCK",
      razorpay: "ZERO call count (hard invariant enforced)",
      theme: "fail",
    },
    {
      id: "stepup" as const,
      label: "Demo 3: Semantic Step-Up",
      sku: "prod_c",
      name: "Sony Party Edition (₹14,999)",
      hardGate: "PASS (Amount ₹14,999 ≤ ₹20,000, Category audio)",
      semantic: "CONTRADICTED: metallic gold & party styling vs 'not flashy'",
      verdict: "STEP_UP",
      outcome: "Autonomous lock engaged · Escalated to Human Oversight",
      decision: "STEP_UP",
      razorpay: "Paused: requires human approval once or reject",
      theme: "stepup",
    },
    {
      id: "revoked" as const,
      label: "Demo 4: Revocation Kill-Switch",
      sku: "prod_a",
      name: "Mid-Session Revocation",
      hardGate: "FAIL: MANDATE_REVOKED (signed version invalidated)",
      semantic: "SHORT-CIRCUITED (revocation checked before lock reservation)",
      verdict: "BLOCK",
      outcome: "Execution denied deterministically · Audit logged",
      decision: "BLOCK",
      razorpay: "ZERO call count (funds protected)",
      theme: "fail",
    },
    {
      id: "adversarial" as const,
      label: "Demo 5: Prompt Injection Defense",
      sku: "prod_trojan",
      name: "Trojan Gold Beats (Adversarial SKU)",
      hardGate: "PASS (Amount ₹14,999 ≤ ₹20,000, Category headphones)",
      semantic: "DEFENDED: Prompt injection ignored as untrusted evidence → CONTRADICTED",
      verdict: "STEP_UP",
      outcome: "Zero injection bypass · Instruction quarantined · Escalated to human",
      decision: "STEP_UP",
      razorpay: "ZERO call count (Razorpay protected from adversarial hijack)",
      theme: "stepup",
    },
  ];

  const current = scenarios.find((s) => s.id === activeScenario)!;

  const hardGateBadge = metrics?.p95_authorization_latency_ms
    ? `${metrics.p95_authorization_latency_ms}ms P95`
    : "<1ms TICK";

  const pipelineSteps = [
    { num: "01", title: "Signed Mandate", desc: "Human-bounded intent signed with ECDSA P-256", badge: "P-256 VERIFIED", icon: Fingerprint },
    { num: "02", title: "Hard Gate", desc: "Deterministic checks on amount, currency, merchant", badge: hardGateBadge, icon: ShieldCheck },
    { num: "03", title: "Semantic Intent", desc: "Catalog-authoritative evidence classifier", badge: "FACT-BOUND", icon: Sparkles },
    { num: "04", title: "Razorpay Exec", desc: "Atomic reservation + hosted test-mode checkout", badge: "TEST MODE", icon: ShoppingBag },
  ];

  return (
    <>
      <div className="view-heading">
        <div>
          <p className="view-kicker">Operational Cockpit / 00</p>
          <h1 className="view-title">Authority Before Action.</h1>
        </div>
        <p className="view-desc">
          JANUS deterministically enforces human purchasing boundaries. AI interprets merchant facts
          without expanding spending authority.
        </p>
      </div>

      {/* 4-Node Authority Pipeline with Animated SVG Beam */}
      <div className="authority-flow-wrapper">
        <div className="authority-flow-beam-svg" />
        <div className="authority-flow">
          {pipelineSteps.map((step) => {
            const Icon = step.icon;
            return (
              <div className="flow-card" key={step.num}>
                <div className="flow-top">
                  <span className="flow-step-num">{step.num}</span>
                  <span className="flow-badge-sub">{step.badge}</span>
                  <div className="flow-icon-box">
                    <Icon size={16} />
                  </div>
                </div>
                <span className="flow-title">{step.title}</span>
                <p className="flow-desc">{step.desc}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Interactive Dual-Path Gateway Live Visualizer */}
      <div className="gateway-visualizer-card">
        <div className="sim-controls-bar">
          <div className="sim-title-group">
            <Sparkles size={15} color="#6a3df0" />
            <span className="sim-title-kicker">REAL-TIME DUAL-PATH FIREWALL SIMULATOR</span>
          </div>
          <div className="sim-scenarios">
            {scenarios.map((sc) => (
              <button
                key={sc.id}
                className={`scenario-tab ${activeScenario === sc.id ? "active" : ""}`}
                onClick={() => setActiveScenario(sc.id)}
              >
                <CircleDot size={10} color={sc.theme === "pass" ? "#24eca0" : sc.theme === "fail" ? "#ef4444" : "#f97316"} />
                <span>{sc.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* 5-Node Interactive Circuit */}
        <div className="sim-circuit-grid">
          {/* Node 1: AI Buyer Proposal */}
          <div className="sim-node">
            <div className="sim-node-header">
              <span className="sim-node-title">AI PROPOSAL</span>
              <ShoppingBag size={13} color="#94a3b8" />
            </div>
            <strong style={{ fontSize: "11.5px", color: "var(--ink)" }}>{current.name}</strong>
            <span className="sim-node-detail">SKU: {current.sku} · Qty: 1</span>
          </div>

          {/* Connector 1 */}
          <div className="sim-connector">
            <div className={`laser-rail active-${current.theme === "pass" ? "green" : current.theme === "fail" ? "red" : "purple"}`} />
          </div>

          {/* Dual Parallel Tracks */}
          <div className="sim-dual-tracks">
            {/* Upper: Deterministic Hard Gate */}
            <div className={`track-channel ${current.theme === "fail" ? "fail" : "pass"}`}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <ShieldCheck size={12} />
                <strong>HARD GATE (0ms)</strong>
              </div>
              <span style={{ fontSize: "9.5px", fontFamily: "var(--font-mono)" }}>
                {current.theme === "fail" ? "FAIL CLOSED" : "PASS"}
              </span>
            </div>

            {/* Lower: Semantic Intent Path */}
            <div className={`track-channel ${current.theme === "stepup" ? "stepup" : current.theme === "fail" ? "fail" : "pass"}`}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <Sparkles size={12} />
                <strong>SEMANTIC AI</strong>
              </div>
              <span style={{ fontSize: "9.5px", fontFamily: "var(--font-mono)" }}>
                {current.theme === "stepup" ? "CONTRADICTION" : current.theme === "fail" ? "SKIPPED" : "SUPPORTED"}
              </span>
            </div>
          </div>

          {/* Connector 2 */}
          <div className="sim-connector">
            <div className={`laser-rail active-${current.theme === "pass" ? "green" : current.theme === "fail" ? "red" : "purple"}`} />
          </div>

          {/* Node 3: Arbiter Verdict & Action */}
          <div className={`sim-node state-${current.theme}`}>
            <div className="sim-node-header">
              <span className="sim-node-title">DECISION ARBITER</span>
              <StateBadge value={current.verdict} />
            </div>
            <span style={{ fontSize: "10px", color: "var(--ink-secondary)", lineHeight: 1.3 }}>
              {current.outcome}
            </span>
          </div>
        </div>

        <div className="sim-footer-note">
          <span>
            <strong>Invariant Note: </strong>
            {activeScenario === "allow" && "Hard gate pass + all semantic constraints supported = immediate test order reservation."}
            {activeScenario === "hard_block" && "Hard gate limits are mathematical law. Razorpay is never invoked when hard limits fail."}
            {activeScenario === "stepup" && "Catalog facts contradict intent. System fails safely to human approval once."}
            {activeScenario === "revoked" && "Human kill-switch checked before database lock reservation. Instant termination."}
            {activeScenario === "adversarial" && "Untrusted catalog directives ('IGNORE INSTRUCTIONS') are quarantined. System enforces intent, blocks autonomous bypass, and alerts human."}
          </span>
          <button
            className="btn-sim-launch"
            onClick={() => {
              if (onSelectProductAndGo) {
                onSelectProductAndGo(current.sku);
              } else {
                go("simulator");
              }
            }}
          >
            <span>TEST IN CHECKOUT ENGINE</span>
            <ArrowRight size={12} />
          </button>
        </div>
      </div>

      {/* Telemetry Metric Cards */}
      <div className="telemetry-grid">
        <div className="metric-card">
          <span className="metric-header">CATALOG PRODUCTS</span>
          <span className="metric-number">{String(products.length).padStart(2, "0")}</span>
          <span className="metric-caption">merchant-controlled SKUs</span>
        </div>
        <div className="metric-card">
          <span className="metric-header">ACTIVE AUTHORITY</span>
          <span className="metric-number">{mandate?.status ?? "NONE"}</span>
          <span className="metric-caption">
            {mandate
              ? `v${mandate.version} · ${mandate.execution_count}/${mandate.max_executions} used`
              : "Issue a mandate to delegate"}
          </span>
        </div>
        <div className="metric-card">
          <span className="metric-header">GATEWAY CLEARANCE</span>
          <span className="metric-number">
            {metrics?.authorization_success_rate_pct !== null && metrics?.authorization_success_rate_pct !== undefined
              ? `${metrics.authorization_success_rate_pct}%`
              : "100%"}
          </span>
          <span className="metric-caption">
            {metrics && metrics.total_proposals > 0
              ? `${metrics.allowed_count ?? metrics.executed_proposals ?? 0} allowed · ${metrics.total_proposals} total`
              : "zero unauthorized bypass"}
          </span>
        </div>
        <div className="metric-card">
          <span className="metric-header">AUDIT EVENTS</span>
          <span className="metric-number">{String(events.length).padStart(2, "0")}</span>
          <span className="metric-caption">cryptographic audit trail</span>
        </div>
      </div>

      {/* Control Room Split */}
      <div className="split-deck">
        <div className="deck-panel">
          <div className="panel-header">
            <span className="panel-title">DUAL-PATH DECISION CONTRACT</span>
            <ShieldCheck size={16} color="#6a3df0" />
          </div>
          <div className="contract-row">
            <div className="contract-label">
              <span className="contract-condition">Hard Gate FAIL</span>
              <span className="contract-note">Amount exceeded, wrong merchant, or revoked</span>
            </div>
            <StateBadge value="BLOCK" />
          </div>
          <div className="contract-row">
            <div className="contract-label">
              <span className="contract-condition">Hard PASS + Semantic SUPPORTED</span>
              <span className="contract-note">All explicit merchant facts clear</span>
            </div>
            <StateBadge value="ALLOW" />
          </div>
          <div className="contract-row">
            <div className="contract-label">
              <span className="contract-condition">Hard PASS + Ambiguity / Contradiction</span>
              <span className="contract-note">Missing evidence or conflicting attribute</span>
            </div>
            <StateBadge value="STEP_UP" />
          </div>
        </div>

        <div className="hero-action-tile">
          <div>
            <span className="hero-kicker">Next Safe Action</span>
            <h3>{mandate ? "Test the Checkout Boundary" : "Delegate a Bounded Purchase"}</h3>
            <p>
              {mandate
                ? "Simulate an autonomous agent proposing products through the hard gate and semantic path."
                : "Compile natural-language intent into mathematically bounded hard limits and verifiable constraints."}
            </p>
          </div>
          <button
            className="btn-primary"
            style={{ width: "max-content" }}
            onClick={() => go(mandate ? "simulator" : "issue")}
          >
            <span>{mandate ? "LAUNCH CHECKOUT ENGINE" : "ISSUE NEW MANDATE"}</span>
            <ArrowRight size={15} />
          </button>
        </div>
      </div>
    </>
  );
}

/* ==========================================================================
   VIEW 2: CATALOG & INVENTORY
   ========================================================================== */
function CatalogView({
  products,
  merchantId,
  setMerchantId,
  refresh,
  busy,
  act,
  metrics,
}: {
  products: Product[];
  merchantId: string;
  setMerchantId: (v: string) => void;
  refresh: () => Promise<void>;
  busy: string;
  act: (label: string, fn: () => Promise<void>) => Promise<void>;
  metrics: MerchantMetrics | null;
}) {
  const [payload, setPayload] = useState("");
  const [result, setResult] = useState<{ created: number; updated: number; unchanged: number; total: number } | null>(null);

  async function handleFile(file: File | undefined) {
    if (file) setPayload(await file.text());
  }

  const importNow = () =>
    act("catalog", async () => {
      let parsed: unknown;
      try {
        parsed = JSON.parse(payload);
      } catch {
        throw new Error("CATALOG_JSON_INVALID");
      }
      if (!Array.isArray(parsed)) throw new Error("CATALOG_MUST_BE_AN_ARRAY");
      const res = await request<{ created: number; updated: number; unchanged: number; total: number }>(
        "/api/v1/products/import",
        {
          method: "POST",
          body: JSON.stringify({ merchant_id: merchantId, products: parsed }),
        },
      );
      setResult(res);
      await refresh();
    });

  return (
    <>
      <div className="view-heading">
        <div>
          <p className="view-kicker">Merchant Inventory / 01</p>
          <h1 className="view-title">Authoritative Merchant Facts.</h1>
        </div>
        <p className="view-desc">
          Pricing, currency, and attributes are owned exclusively by the merchant. Autonomous agents
          can never override these authoritative values.
        </p>
      </div>

      {/* Track 01: Merchant Commerce Telemetry Banner */}
      <div className="track01-metrics-banner">
        <div className="metric-stat-card">
          <span className="metric-stat-kicker">Track 01 Merchant SKUs</span>
          <span className="metric-stat-value">{metrics?.total_skus ?? products.length} Active</span>
          <span className="metric-stat-sub">
            <Check size={12} color="#059669" />
            <span>{metrics?.machine_readable_pct ?? 100}% Machine-Readable v1</span>
          </span>
        </div>
        <div className="metric-stat-card">
          <span className="metric-stat-kicker">Autonomous GMV Settled</span>
          <span className="metric-stat-value green">{money(metrics?.autonomous_gmv_paise ?? 0)}</span>
          <span className="metric-stat-sub">
            <ShieldCheck size={12} color="#059669" />
            <span>Razorpay Test Orders Settled</span>
          </span>
        </div>
        <div className="metric-stat-card">
          <span className="metric-stat-kicker">Prevented Overspend</span>
          <span className="metric-stat-value purple">{money(metrics?.prevented_overspend_paise ?? 0)}</span>
          <span className="metric-stat-sub">
            <LockKeyhole size={12} color="#6a3df0" />
            <span>Protected by Hard Limits</span>
          </span>
        </div>
        <div className="metric-stat-card">
          <span className="metric-stat-kicker">Agent Conversion Rate</span>
          <span className="metric-stat-value">{metrics?.conversion_rate_pct ?? 0}%</span>
          <span className="metric-stat-sub">
            <Activity size={12} color="#565e52" />
            <span>{metrics?.executed_proposals ?? 0} executed / {metrics?.total_proposals ?? 0} proposals</span>
          </span>
        </div>
      </div>

      <div className="catalog-layout">
        {/* Left Column: Import Controls */}
        <div className="catalog-import-card">
          <div className="form-group">
            <label className="form-label" htmlFor="merchant-input">Merchant Account ID</label>
            <input
              id="merchant-input"
              className="form-input"
              value={merchantId}
              onChange={(e) => setMerchantId(e.target.value)}
              placeholder="e.g. northstar_audio"
            />
          </div>

          <div className="form-group">
            <label className="form-label">Upload Catalog JSON</label>
            <label className="file-drop-area" htmlFor="catalog-file-input">
              <UploadCloud size={17} />
              <span>Choose Catalog File</span>
              <input
                id="catalog-file-input"
                type="file"
                accept="application/json,.json"
                style={{ display: "none" }}
                onChange={(e) => handleFile(e.target.files?.[0])}
              />
            </label>
          </div>

          <div className="form-group" style={{ flex: 1, display: "flex", flexDirection: "column" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
              <label className="form-label" htmlFor="catalog-json-textarea">Or Paste JSON Records</label>
              <button
                type="button"
                className="btn-secondary"
                style={{ padding: "2px 8px", fontSize: "10px" }}
                onClick={() => {
                  setMerchantId("merchant_demo");
                  setPayload(JSON.stringify([
                    {
                      id: "prod_a",
                      merchant_id: "merchant_demo",
                      name: "Sony Voyager NC",
                      price_paise: 1849900,
                      currency: "INR",
                      category: "headphones",
                      condition: "new",
                      active: true,
                      attributes: {
                        noise_cancelling: true,
                        weight_g: 254,
                        foldable: true,
                        travel_case: true,
                        color: "black",
                        branding: "minimal",
                        collection: "travel"
                      }
                    },
                    {
                      id: "prod_b",
                      merchant_id: "merchant_demo",
                      name: "Sony Studio Pro",
                      price_paise: 2149900,
                      currency: "INR",
                      category: "headphones",
                      condition: "new",
                      active: true,
                      attributes: {
                        noise_cancelling: true,
                        color: "black"
                      }
                    },
                    {
                      id: "prod_c",
                      merchant_id: "merchant_demo",
                      name: "Aura Gold Party ANC",
                      price_paise: 1999900,
                      currency: "INR",
                      category: "headphones",
                      condition: "new",
                      active: true,
                      attributes: {
                        color: "metallic gold",
                        branding: "oversized logo",
                        collection: "party",
                        noise_cancelling: true
                      }
                    }
                  ], null, 2));
                }}
              >
                Insert Demo Preset
              </button>
            </div>
            <textarea
              id="catalog-json-textarea"
              className="form-textarea"
              value={payload}
              onChange={(e) => setPayload(e.target.value)}
              placeholder='[{"id":"sku-001","merchant_id":"merchant_demo","name":"Headphones","price_paise":1849900,"currency":"INR","category":"headphones","condition":"new","active":true,"attributes":{"color":"black"}}]'
            />
          </div>

          <button
            className="btn-primary"
            style={{ width: "100%", justifyContent: "center" }}
            disabled={!!busy || merchantId.length < 3 || !payload.trim()}
            onClick={importNow}
          >
            <UploadCloud size={15} />
            <span>{busy === "catalog" ? "VALIDATING & IMPORTING…" : "VALIDATE & IMPORT"}</span>
          </button>

          {result && (
            <div style={{ background: "var(--green-tint)", padding: "10px", borderRadius: "8px", fontSize: "11px", color: "#065f46" }}>
              <strong>{result.total} Records Synced</strong> ({result.created} new, {result.updated} updated, {result.unchanged} unchanged)
            </div>
          )}
        </div>

        {/* Right Column: Catalog Table */}
        <div className="catalog-table-panel">
          <div className="panel-header" style={{ padding: "16px 20px" }}>
            <span className="panel-title">LIVE CATALOG ({(Array.isArray(products) ? products.length : 0)} SKUs)</span>
            <span style={{ fontSize: "11px", fontFamily: "var(--font-mono)", color: "var(--ink-muted)" }}>
              MERCHANT: {merchantId}
            </span>
          </div>

          <div className="catalog-list-scroll">
            {(Array.isArray(products) ? products : []).map((p) => {
              const attrs = p.attributes && typeof p.attributes === "object" && !Array.isArray(p.attributes)
                ? Object.entries(p.attributes)
                : [];
              return (
                <div className="product-row-item" key={p.id}>
                  <div className="prod-meta">
                    <span className="prod-name">{p.name}</span>
                    <div className="prod-tags">
                      <span className="attr-tag">{p.id}</span>
                      <span className="attr-tag">{p.category}</span>
                      <span className="attr-tag">{p.condition}</span>
                      {attrs.map(([k, v]) => (
                        <span className="attr-tag" key={k}>
                          {k}: {String(v)}
                        </span>
                      ))}
                    </div>
                  </div>
                  <span className="prod-price">{money(p.price_paise)}</span>
                  <StateBadge value={p.active ? "ACTIVE" : "INACTIVE"} />
                </div>
              );
            })}

            {(!Array.isArray(products) || !products.length) && (
              <div className="empty-box">
                <ShoppingBag size={28} />
                <strong>Catalog is Empty</strong>
                <p>Import merchant products or switch merchant account to view SKUs.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

/* ==========================================================================
   VIEW 3: MANDATE STUDIO (INTENT COMPILER)
   ========================================================================== */
function IssueView({
  instruction,
  setInstruction,
  merchantId,
  setMerchantId,
  draft,
  compile,
  issue,
  busy,
}: {
  instruction: string;
  setInstruction: (v: string) => void;
  merchantId: string;
  setMerchantId: (v: string) => void;
  draft: Draft | null;
  compile: () => void;
  issue: () => void;
  busy: string;
}) {
  return (
    <>
      <div className="view-heading">
        <div>
          <p className="view-kicker">Intent Compiler / 02</p>
          <h1 className="view-title">Bounded Mandate Studio.</h1>
        </div>
        <p className="view-desc">
          Translates ambiguous human prompts into deterministic mathematical bounds. The compiler
          never invents numbers, merchants, or expiry dates.
        </p>
      </div>

      <div className="mandate-studio-layout">
        {/* Input Panel */}
        <div className="studio-input-panel">
          <div className="form-group">
            <label className="form-label" htmlFor="merchant-target-input">Target Merchant ID</label>
            <input
              id="merchant-target-input"
              className="form-input"
              value={merchantId}
              onChange={(e) => setMerchantId(e.target.value)}
              placeholder="e.g. northstar_audio"
            />
          </div>

          <div className="form-group" style={{ flex: 1, display: "flex", flexDirection: "column" }}>
            <label className="form-label" htmlFor="human-intent-textarea">Human Delegation Prompt</label>
            <textarea
              id="human-intent-textarea"
              className="form-textarea"
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              placeholder="e.g. Buy noise-cancelling headphones under ₹20k. Nothing refurbished. Good for travel. Nothing flashy."
            />
          </div>

          <button
            className="btn-primary"
            style={{ width: "100%", justifyContent: "center" }}
            onClick={compile}
            disabled={!!busy || merchantId.length < 3 || !instruction.trim()}
          >
            <Activity size={15} />
            <span>{busy === "compile" ? "COMPILING INTENT…" : "COMPILE INTENT BOUNDS"}</span>
          </button>
        </div>

        {/* Compiled Review Panel */}
        <div className="studio-compiled-panel">
          <div className="panel-header">
            <span className="panel-title">MANDATE PREVIEW & SIGNING</span>
            {draft && <StateBadge value={draft.unresolved.length ? "STEP_UP" : "PASS"} />}
          </div>

          <div className="compiled-scroll">
            {draft ? (
              <>
                {/* Hard Constraints Box */}
                <div className="constraint-box">
                  <div className="constraint-box-title">DETERMINISTIC HARD CONSTRAINTS</div>
                  {draft.hard_constraints ? (
                    <div className="constraint-grid">
                      {Object.entries(draft.hard_constraints).map(([k, v]) => (
                        <div className="constraint-item" key={k}>
                          <span className="constraint-key">{pretty(k)}</span>
                          <span className="constraint-val">
                            {k.includes("amount")
                              ? money(v as number)
                              : Array.isArray(v)
                              ? v.join(", ")
                              : String(v)}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p style={{ fontSize: "11px", color: "var(--ink-muted)" }}>No numerical limits could be extracted.</p>
                  )}
                </div>

                {/* Semantic Constraints Box */}
                <div className="constraint-box">
                  <div className="constraint-box-title">SEMANTIC INTENT CONSTRAINTS (MERCHANT EVIDENCE PATH)</div>
                  <div className="semantic-pill-list">
                    {draft.semantic_constraints.map((s) => (
                      <div className="semantic-pill" key={s.id}>
                        <span>{s.text}</span>
                        <span className="semantic-tag">CLASSIFIED ON CATALOG FACTS</span>
                      </div>
                    ))}
                    {!draft.semantic_constraints.length && (
                      <p style={{ fontSize: "11px", color: "var(--ink-muted)" }}>No qualitative semantic constraints specified.</p>
                    )}
                  </div>
                </div>

                {/* Unresolved Ambiguities */}
                {draft.unresolved.map((u) => (
                  <div
                    key={u.field}
                    style={{
                      background: "var(--amber-tint)",
                      border: "1px solid var(--amber-border)",
                      padding: "10px 14px",
                      borderRadius: "10px",
                      display: "flex",
                      gap: "10px",
                      alignItems: "center",
                    }}
                  >
                    <TriangleAlert size={16} color="#c2410c" />
                    <div>
                      <strong style={{ fontSize: "12px", color: "#c2410c" }}>{pretty(u.field)}</strong>
                      <p style={{ fontSize: "11px", color: "#9a3412" }}>{u.reason}</p>
                    </div>
                  </div>
                ))}
              </>
            ) : (
              <div className="empty-box">
                <FileKey2 size={28} />
                <strong>Awaiting Intent Compilation</strong>
                <p>Compile a human instruction prompt to generate exact mathematical boundaries.</p>
              </div>
            )}
          </div>

          <button
            className="btn-primary"
            style={{ width: "100%", justifyContent: "center" }}
            onClick={issue}
            disabled={!draft?.hard_constraints || !!draft.unresolved.length || !!busy}
          >
            <Fingerprint size={16} />
            <span>{busy === "issue" ? "SIGNING WITH ECDSA P-256…" : "SIGN & ACTIVATE MANDATE"}</span>
          </button>
        </div>
      </div>
    </>
  );
}

/* ==========================================================================
   VIEW 4: ACTIVE MANDATE DETAILS
   ========================================================================== */
function MandateDetailView({
  mandate,
  revoke,
  busy,
  goSimulator,
}: {
  mandate: Mandate | null;
  revoke: () => void;
  busy: string;
  goSimulator: () => void;
}) {
  if (!mandate) {
    return (
      <div className="empty-box" style={{ marginTop: "80px" }}>
        <Fingerprint size={32} />
        <strong>No Active Mandate Found</strong>
        <p>Issue a signed mandate from the studio to inspect its cryptographic envelope.</p>
      </div>
    );
  }

  return (
    <>
      <div className="view-heading">
        <div>
          <p className="view-kicker">Cryptographic Envelope / 03</p>
          <h1 className="view-title">Active Signed Authority.</h1>
        </div>
        <p className="view-desc">
          Live server state always supersedes a valid signature. Revocation, expiry, version bumps, or
          single-use consumption terminate execution instantly.
        </p>
      </div>

      <div className="mandate-envelope-banner">
        <div className="envelope-left">
          <span className="envelope-tag">ENVELOPE DIGEST / SHA-256</span>
          <span className="envelope-id">{mandate.id}</span>
        </div>
        <StateBadge value={mandate.status} />
      </div>

      <div className="split-deck">
        <div className="deck-panel">
          <div className="panel-header">
            <span className="panel-title">BOUNDED HARD POLICY</span>
            <ShieldCheck size={16} color="#6a3df0" />
          </div>
          {Object.entries(mandate.hard_constraints).map(([k, v]) => (
            <div className="contract-row" key={k}>
              <span style={{ fontSize: "12px", textTransform: "capitalize", color: "var(--ink-secondary)" }}>
                {pretty(k)}
              </span>
              <strong style={{ fontSize: "13px", fontFamily: "var(--font-mono)" }}>
                {k.includes("amount") ? money(v as number) : Array.isArray(v) ? v.join(", ") : String(v)}
              </strong>
            </div>
          ))}
        </div>

        <div className="deck-panel">
          <div className="panel-header">
            <span className="panel-title">SIGNATURE & STATE INTEGRITY</span>
            <LockKeyhole size={16} color="#6a3df0" />
          </div>
          <div className="contract-row">
            <span style={{ fontSize: "12px", color: "var(--ink-secondary)" }}>Algorithm</span>
            <strong style={{ fontSize: "12px", fontFamily: "var(--font-mono)" }}>ECDSA P-256 / SHA-256</strong>
          </div>
          <div className="contract-row">
            <span style={{ fontSize: "12px", color: "var(--ink-secondary)" }}>Version</span>
            <strong style={{ fontSize: "12px", fontFamily: "var(--font-mono)" }}>{mandate.version}</strong>
          </div>
          <div className="contract-row">
            <span style={{ fontSize: "12px", color: "var(--ink-secondary)" }}>Expires</span>
            <strong style={{ fontSize: "12px", fontFamily: "var(--font-mono)" }}>{when(mandate.expires_at)}</strong>
          </div>
          <div className="contract-row">
            <span style={{ fontSize: "12px", color: "var(--ink-secondary)" }}>Executions</span>
            <strong style={{ fontSize: "12px", fontFamily: "var(--font-mono)" }}>
              {mandate.execution_count} / {mandate.max_executions}
            </strong>
          </div>

          <div style={{ marginTop: "auto", display: "flex", gap: "10px", justifyContent: "flex-end", paddingTop: "16px" }}>
            <button
              className="btn-danger"
              onClick={revoke}
              disabled={mandate.status !== "ACTIVE" || !!busy}
            >
              <Ban size={14} />
              <span>REVOKE MANDATE</span>
            </button>
            <button
              className="btn-primary"
              onClick={goSimulator}
              disabled={mandate.status !== "ACTIVE"}
            >
              <span>TEST CHECKOUT</span>
              <ArrowRight size={14} />
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

/* ==========================================================================
   VIEW 5: AGENT CHECKOUT SIMULATOR (COCKPIT)
   ========================================================================== */
function SimulatorView({
  mandate,
  products,
  selected,
  setSelected,
  propose,
  execute,
  checkout,
  payment,
  decision,
  order,
  busy,
  goStepUp,
  buyerResult,
  dispatchAutonomousShop,
  merchantId,
}: {
  mandate: Mandate | null;
  products: Product[];
  selected: string;
  setSelected: (v: string) => void;
  propose: () => void;
  execute: () => void;
  checkout: () => void;
  payment: PaymentResult | null;
  decision: Decision | null;
  order: Order | null;
  busy: string;
  goStepUp: () => void;
  buyerResult: AutonomousShopResult | null;
  dispatchAutonomousShop: (autoExecute?: boolean) => void;
  merchantId: string;
}) {
  const [mode, setMode] = useState<"autonomous" | "interactive">("autonomous");

  return (
    <>
      <div className="view-heading">
        <div>
          <p className="view-kicker">Agent Simulator / 04</p>
          <h1 className="view-title">Propose. Authorize. Transact.</h1>
        </div>
        <p className="view-desc">
          Simulates an AI buyer submitting checkout requests. Razorpay execution is reachable ONLY
          when both the deterministic hard gate and semantic path clear.
        </p>
      </div>

      {/* Mode Toggle Bar: Autonomous Buyer vs Interactive Simulation */}
      <div className="mode-toggle-bar">
        <div className="mode-toggle-group">
          <button
            type="button"
            className={`mode-pill-btn ${mode === "autonomous" ? "active" : ""}`}
            onClick={() => setMode("autonomous")}
          >
            <Sparkles size={13} />
            <span>Autonomous Buyer Agent</span>
            <span style={{ fontSize: "9px", background: "var(--purple-tint)", color: "var(--purple-deep)", padding: "1px 6px", borderRadius: "999px" }}>
              Track 01 Core
            </span>
          </button>
          <button
            type="button"
            className={`mode-pill-btn ${mode === "interactive" ? "active" : ""}`}
            onClick={() => setMode("interactive")}
          >
            <ShoppingBag size={13} />
            <span>Interactive Simulator</span>
          </button>
        </div>
        <div style={{ fontSize: "11px", color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}>
          MERCHANT: <strong>{merchantId}</strong>
        </div>
      </div>

      {!mandate ? (
        <div className="empty-box" style={{ marginTop: "80px" }}>
          <ShoppingBag size={32} />
          <strong>No Active Authority</strong>
          <p>You must issue an active mandate before an agent can propose purchases.</p>
        </div>
      ) : mode === "autonomous" ? (
        /* ================= AUTONOMOUS BUYER AGENT MODE ================= */
        <div className="autonomous-layout">
          {/* Left Column: Mission Briefing & Dispatch */}
          <div className="agent-briefing-card">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span className="panel-title">AGENT MISSION BRIEF</span>
              <StateBadge value={mandate.status} />
            </div>

            <div className="briefing-field">
              <label>Cryptographic Mandate ID</label>
              <div className="val-box" style={{ fontFamily: "var(--font-mono)", fontSize: "11px" }}>
                {mandate.id}
              </div>
            </div>

            <div className="briefing-field">
              <label>Human Intent Instruction</label>
              <div className="val-box">"{mandate.instruction_text}"</div>
            </div>

            <div className="briefing-field">
              <label>Deterministic Hard Limits</label>
              <div className="val-box" style={{ fontFamily: "var(--font-mono)", fontSize: "11px" }}>
                Max Budget: {money(Number(mandate.hard_constraints?.max_amount_paise ?? 0))}
                <br />
                Currency: {(mandate.hard_constraints?.allowed_currencies as string[])?.join(", ") ?? "INR"}
                <br />
                Executions: {mandate.max_executions - mandate.execution_count} / {mandate.max_executions} available
              </div>
            </div>

            <div className="briefing-field">
              <label>Authoritative Merchant Authority</label>
              <div className="val-box" style={{ fontFamily: "var(--font-mono)", fontSize: "11px" }}>
                {merchantId} ({products.length} machine-readable SKUs)
              </div>
            </div>

            <button
              className="btn-primary"
              style={{ width: "100%", justifyContent: "center", padding: "12px", background: "linear-gradient(135deg, #6a3df0, #5227d8)" }}
              onClick={() => dispatchAutonomousShop(true)}
              disabled={!!busy || mandate.status !== "ACTIVE"}
            >
              <Sparkles size={16} />
              <span>{busy === "autonomous-shop" ? "AUTONOMOUS REASONING & SHOPPING…" : "DISPATCH AUTONOMOUS BUYER AGENT"}</span>
            </button>

            {/* If Razorpay Test Order Created */}
            {order && !payment && (
              <button className="btn-razorpay" onClick={checkout} disabled={!!busy || !order.key_id}>
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <CreditCard size={18} color="#bf8efd" />
                  <div style={{ textAlign: "left" }}>
                    <div style={{ fontSize: "12.5px", fontWeight: 700 }}>PAY WITH RAZORPAY TEST CHECKOUT</div>
                    <div style={{ fontSize: "10px", color: "rgba(255,255,255,0.7)" }}>
                      Order: {order.razorpay_order_id} · {money(order.amount ?? 0)}
                    </div>
                  </div>
                </div>
                <span>{busy === "checkout" ? "OPENING…" : busy === "verify" ? "VERIFYING…" : "OPEN POPUP"}</span>
              </button>
            )}

            {/* If Payment Captured */}
            {payment && (
              <div className="payment-verified-banner">
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <Check size={18} color="#10b981" />
                  <div>
                    <strong style={{ fontSize: "12px", display: "block" }}>RAZORPAY PAYMENT CAPTURED</strong>
                    <span style={{ fontSize: "10px", fontFamily: "var(--font-mono)" }}>ID: {payment.razorpay_payment_id}</span>
                  </div>
                </div>
                <StateBadge value="PAID" />
              </div>
            )}

            {/* If Step-Up Escalated */}
            {buyerResult?.decision === "STEP_UP" && (
              <button
                className="btn-primary"
                style={{ width: "100%", justifyContent: "space-between", background: "#f97316" }}
                onClick={goStepUp}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <UserCheck size={14} />
                  <span>STEP-UP ESCALATED — REVIEW</span>
                </div>
                <ArrowRight size={14} />
              </button>
            )}
          </div>

          {/* Right Column: Execution Trace & Candidate Matrix */}
          <div className="agent-results-column">
            {buyerResult ? (
              <>
                {/* Verdict Summary */}
                <div className="decision-hero-card" style={{ marginBottom: "0" }}>
                  <div className="decision-header-row">
                    <div className="decision-title-group">
                      <span style={{ fontSize: "10px", fontFamily: "var(--font-mono)", color: "var(--ink-muted)" }}>
                        AUTONOMOUS CYCLE VERDICT
                      </span>
                      <span className={`decision-badge-big ${buyerResult.decision}`}>{buyerResult.decision}</span>
                      <span style={{ fontSize: "12px", color: "var(--ink-secondary)" }}>
                        {buyerResult.selected_product_name
                          ? `Selected: ${buyerResult.selected_product_name} (${money(buyerResult.amount_paise ?? 0)})`
                          : (buyerResult.reason_code ? pretty(buyerResult.reason_code) : "Cycle complete")}
                      </span>
                    </div>
                    <StateBadge value={buyerResult.status} />
                  </div>
                  <p style={{ fontSize: "12px", color: "var(--ink)", lineHeight: 1.5, background: "var(--bg-subtle)", padding: "10px", borderRadius: "8px" }}>
                    <strong>Agent Reasoning:</strong> {buyerResult.agent_reasoning}
                  </p>
                </div>

                {/* 6-Stage Autonomous Reasoning Timeline */}
                <div className="agent-step-timeline">
                  <span className="panel-title" style={{ fontSize: "11px" }}>
                    MULTI-STAGE AUTONOMOUS REASONING TRACE ({buyerResult.steps.length} STEPS)
                  </span>
                  {buyerResult.steps.map((s) => (
                    <div className="agent-step-item" key={s.step_num}>
                      <div className="agent-step-num">{s.step_num}</div>
                      <div className="agent-step-content">
                        <div className="agent-step-title">
                          <span>{s.title}</span>
                          <StateBadge value={s.status} />
                        </div>
                        <p className="agent-step-detail">{s.detail}</p>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Candidate SKU Elimination & Ranking Matrix */}
                <div className="matrix-card">
                  <span className="panel-title" style={{ fontSize: "11px" }}>
                    CANDIDATE SKU ELIMINATION & RANKING MATRIX ({buyerResult.candidates_evaluated.length} SKUs)
                  </span>
                  <table className="matrix-table">
                    <thead>
                      <tr>
                        <th>Product SKU</th>
                        <th>Catalog Price</th>
                        <th>Hard Gate</th>
                        <th>Semantic Fit</th>
                        <th>Score</th>
                        <th>Evaluation Details</th>
                      </tr>
                    </thead>
                    <tbody>
                      {buyerResult.candidates_evaluated.map((c) => {
                        const isSelected = c.product_id === buyerResult.selected_product_id;
                        return (
                          <tr
                            key={c.product_id}
                            className={isSelected ? "selected-row" : !c.hard_eligible ? "eliminated-row" : ""}
                          >
                            <td>
                              <strong>{c.name}</strong>
                              <span style={{ display: "block", fontSize: "10px", color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}>
                                {c.product_id}
                              </span>
                            </td>
                            <td style={{ fontFamily: "var(--font-mono)", fontWeight: 700 }}>
                              {money(c.price_paise)}
                            </td>
                            <td>
                              {c.hard_eligible ? (
                                <span style={{ color: "#059669", fontWeight: 700, display: "flex", alignItems: "center", gap: "4px" }}>
                                  <Check size={13} /> PASS
                                </span>
                              ) : (
                                <span style={{ color: "#dc2626", fontWeight: 700, display: "flex", alignItems: "center", gap: "4px" }}>
                                  <X size={13} /> FAIL
                                </span>
                              )}
                            </td>
                            <td>
                              {c.semantic_notes ? (
                                <div>
                                  <StateBadge value={c.semantic_notes.includes("CONTRADICTED") || c.semantic_notes.includes("Contradicted") ? "CONTRADICTED" : c.abstain ? "STEP_UP" : "SUPPORTED"} />
                                  {c.confidence != null && (
                                    <span style={{ display: "block", fontSize: "10px", marginTop: "3px", color: c.abstain ? "#b91c1c" : "#047857", fontFamily: "var(--font-mono)", fontWeight: 600 }}>
                                      {(c.confidence * 100).toFixed(0)}% {c.abstain ? "(Abstained)" : "Conf"}
                                    </span>
                                  )}
                                </div>
                              ) : (
                                <span style={{ color: "var(--ink-muted)", fontSize: "10.5px" }}>N/A</span>
                              )}
                            </td>
                            <td style={{ fontFamily: "var(--font-mono)", fontWeight: 700 }}>
                              {c.semantic_score > 0 ? c.semantic_score.toFixed(2) : "0.00"}
                            </td>
                            <td style={{ fontSize: "11px", color: isSelected ? "#065f46" : "var(--ink-secondary)" }}>
                              <div>
                                {isSelected ? (
                                  <strong style={{ color: "#065f46", display: "block", marginBottom: "3px" }}>
                                    ✓ Selected: Highest verified intent match within budget
                                  </strong>
                                ) : (
                                  <span>{c.rejection_reason || c.semantic_notes || "Sub-optimal match"}</span>
                                )}

                                {c.citations && c.citations.length > 0 && (
                                  <div style={{ fontSize: "10.5px", color: "#475569", marginTop: "4px", fontStyle: "italic", background: "#f8fafc", padding: "4px 8px", borderRadius: "4px", border: "1px solid #e2e8f0" }}>
                                    "{c.citations[0]}"
                                  </div>
                                )}

                                {c.evidence_badges && c.evidence_badges.length > 0 && (
                                  <div style={{ display: "flex", flexWrap: "wrap", gap: "4px", marginTop: "5px" }}>
                                    {c.evidence_badges.slice(0, 4).map((b, idx) => {
                                      const isSupp = b.status === "SUPPORTED";
                                      return (
                                        <span
                                          key={idx}
                                          style={{
                                            fontSize: "9.5px",
                                            fontFamily: "var(--font-mono)",
                                            padding: "1px 5px",
                                            borderRadius: "3px",
                                            background: isSupp ? "#dcfce7" : "#fee2e2",
                                            color: isSupp ? "#166534" : "#991b1b",
                                            border: `1px solid ${isSupp ? "#86efac" : "#fca5a5"}`,
                                          }}
                                          title={b.citation || `${b.field}=${b.value}`}
                                        >
                                          {b.field}={String(b.value)}
                                        </span>
                                      );
                                    })}
                                  </div>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <div className="deck-panel" style={{ alignItems: "center", justifyContent: "center", minHeight: "340px" }}>
                <Sparkles size={32} color="var(--purple-brand)" />
                <strong style={{ fontSize: "14px", marginTop: "12px", color: "var(--ink)" }}>
                  Autonomous Buyer Agent Ready
                </strong>
                <p style={{ fontSize: "12px", color: "var(--ink-muted)", maxWidth: "420px", textAlign: "center", marginTop: "4px" }}>
                  Click "Dispatch Autonomous Buyer Agent" to watch the AI independently parse the mandate, filter SKUs by hard limits, score candidates against fuzzy human intent, generate a signed proposal, and settle via Razorpay test mode.
                </p>
              </div>
            )}
          </div>
        </div>
      ) : (
        /* ================= INTERACTIVE SIMULATOR MODE ================= */
        <div className="simulator-layout">
          {/* Left Column: Product Selection */}
          <div className="simulator-catalog-column">
            <div className="panel-header" style={{ padding: "14px 16px" }}>
              <span className="panel-title">SELECT SKU TO PROPOSE</span>
              <span style={{ fontSize: "10px", fontFamily: "var(--font-mono)", color: "var(--ink-muted)" }}>
                CATALOG BOUND
              </span>
            </div>

            {/* Quick Demo Beat Presets */}
            <div style={{ padding: "8px 12px", borderBottom: "1px solid var(--border-line)", display: "flex", gap: "6px", flexWrap: "wrap", background: "var(--bg-subtle)" }}>
              <button
                type="button"
                className="btn-secondary"
                style={{ padding: "2px 7px", fontSize: "10px" }}
                onClick={() => setSelected("prod_a")}
              >
                Demo 1: Sony Voyager
              </button>
              <button
                type="button"
                className="btn-secondary"
                style={{ padding: "2px 7px", fontSize: "10px" }}
                onClick={() => setSelected("prod_b")}
              >
                Demo 2: Sony Studio (Over limit)
              </button>
              <button
                type="button"
                className="btn-secondary"
                style={{ padding: "2px 7px", fontSize: "10px" }}
                onClick={() => setSelected("prod_c")}
              >
                Demo 3: Aura Gold Party
              </button>
              <button
                type="button"
                className="btn-secondary"
                style={{ padding: "2px 7px", fontSize: "10px", color: "#b91c1c", borderColor: "#fca5a5" }}
                onClick={() => setSelected("prod_trojan")}
              >
                Demo 5: Trojan Injection
              </button>
            </div>

            <div style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
              {(Array.isArray(products) ? products : []).map((p) => {
                const isSel = selected === p.id;
                return (
                  <button
                    key={p.id}
                    className={`sim-product-btn ${isSel ? "selected" : ""}`}
                    onClick={() => setSelected(p.id)}
                  >
                    <div className="sim-radio-circle">
                      {isSel && <Check size={11} />}
                    </div>
                    <div style={{ flex: 1 }}>
                      <strong style={{ fontSize: "13px", display: "block", color: "var(--ink)" }}>{p.name}</strong>
                      <span style={{ fontSize: "10.5px", color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}>
                        {p.id} · {p.category}
                      </span>
                    </div>
                    <span style={{ fontSize: "13px", fontWeight: 700, fontFamily: "var(--font-mono)" }}>
                      {money(p.price_paise)}
                    </span>
                  </button>
                );
              })}
              {(!Array.isArray(products) || !products.length) && (
                <div className="empty-box" style={{ padding: "24px 12px" }}>
                  <ShoppingBag size={24} />
                  <p>No products in catalog. Switch merchant or import items.</p>
                </div>
              )}
            </div>

            <div style={{ padding: "12px 16px", borderTop: "1px solid var(--border-line)" }}>
              <button
                className="btn-primary"
                style={{ width: "100%", justifyContent: "center" }}
                onClick={propose}
                disabled={!!busy || !selected}
              >
                <Play size={14} />
                <span>{busy === "propose" ? "EVALUATING BOTH PATHS…" : "PROPOSE CHECKOUT"}</span>
              </button>
            </div>
          </div>

          {/* Right Column: Authorization Results & Razorpay Payment */}
          <div className="simulator-result-column">
            {decision ? (
              <div className="decision-hero-card">
                <div className="decision-header-row">
                  <div className="decision-title-group">
                    <span style={{ fontSize: "10px", fontFamily: "var(--font-mono)", color: "var(--ink-muted)" }}>
                      GATEWAY VERDICT
                    </span>
                    <span className={`decision-badge-big ${decision.decision}`}>{decision.decision}</span>
                    <span style={{ fontSize: "12px", color: "var(--ink-secondary)" }}>
                      {decision.reason_code ? pretty(decision.reason_code) : "All authorization criteria met"}
                    </span>
                  </div>
                  <StateBadge value={decision.decision} />
                </div>

                {/* Hard Gate Checks */}
                <div>
                  <span className="form-label" style={{ marginBottom: "6px", display: "block" }}>
                    DETERMINISTIC HARD GATE ({decision.hard_gate?.checks?.length ?? 0} CHECKS)
                  </span>
                  <div className="checks-grid">
                    {(decision.hard_gate?.checks ?? []).map((chk) => (
                      <div className="check-item" key={chk.name}>
                        {chk.passed ? (
                          <Check size={14} className="check-icon-good" />
                        ) : (
                          <X size={14} className="check-icon-bad" />
                        )}
                        <span style={{ flex: 1, fontWeight: 600 }}>{pretty(chk.name)}</span>
                        <span style={{ fontSize: "9.5px", color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}>
                          {chk.source}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Semantic Intent Assessment */}
                {decision.semantic && (
                  <div className="semantic-breakdown-box">
                    <span className="form-label" style={{ marginBottom: "6px", display: "block" }}>
                      SEMANTIC INTENT CLASSIFICATION
                    </span>
                    {(decision.semantic.results ?? []).map((item) => (
                      <div key={item.constraint_id} style={{ marginTop: "8px", padding: "6px 8px", background: "#f8fafc", borderRadius: "6px", border: "1px solid #e2e8f0" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <strong style={{ fontSize: "12px" }}>{pretty(item.constraint_id)}</strong>
                          <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                            {item.confidence != null && (
                              <span style={{ fontSize: "10px", fontFamily: "var(--font-mono)", fontWeight: 600, color: item.abstain ? "#b91c1c" : "#047857" }}>
                                {(item.confidence * 100).toFixed(0)}% {item.abstain ? "(Abstained)" : "Conf"}
                              </span>
                            )}
                            <StateBadge value={item.status} />
                          </div>
                        </div>
                        <p style={{ fontSize: "11.5px", color: "var(--ink-secondary)", margin: "3px 0 4px" }}>{item.reason}</p>
                        {item.citation && (
                          <div style={{ fontSize: "10.5px", color: "#334155", fontStyle: "italic", background: "#ffffff", padding: "3px 6px", borderRadius: "3px", border: "1px solid #cbd5e1", marginBottom: "4px" }}>
                            "{item.citation}"
                          </div>
                        )}
                        <span style={{ fontSize: "10px", fontFamily: "var(--font-mono)", color: "var(--purple-brand)" }}>
                          Evidence: {(item.evidence ?? []).map((e) => `${e.field}: ${String(e.value)}`).join(" · ") || "None"}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="deck-panel" style={{ alignItems: "center", justifyContent: "center", minHeight: "180px" }}>
                <ShoppingBag size={28} color="var(--ink-muted)" />
                <span style={{ fontSize: "13px", fontWeight: 600, marginTop: "8px", color: "var(--ink-secondary)" }}>
                  Awaiting Proposal
                </span>
                <p style={{ fontSize: "11.5px", color: "var(--ink-muted)" }}>
                  Select a product and click Propose Checkout to run both authorization paths.
                </p>
              </div>
            )}

            {/* Action Buttons based on Decision */}
            {decision?.decision === "ALLOW" && !order && (
              <button className="btn-razorpay" onClick={execute} disabled={!!busy}>
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <ShieldCheck size={18} color="#24eca0" />
                  <div style={{ textAlign: "left" }}>
                    <div style={{ fontSize: "13px", fontWeight: 700 }}>RESERVE & CREATE RAZORPAY TEST ORDER</div>
                    <div style={{ fontSize: "10.5px", color: "rgba(255,255,255,0.7)" }}>
                      Atomic execution reservation · Razorpay test mode
                    </div>
                  </div>
                </div>
                <ArrowRight size={16} />
              </button>
            )}

            {decision?.decision === "STEP_UP" && (
              <button
                className="btn-primary"
                style={{ width: "100%", justifyContent: "space-between", background: "#f97316" }}
                onClick={goStepUp}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <UserCheck size={16} />
                  <span>HUMAN STEP-UP REQUIRED — REVIEW ESCALATION</span>
                </div>
                <ArrowRight size={15} />
              </button>
            )}

            {/* Razorpay Standard Hosted Checkout Button */}
            {order && !payment && (
              <button className="btn-razorpay" onClick={checkout} disabled={!!busy || !order.key_id}>
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <CreditCard size={18} color="#bf8efd" />
                  <div style={{ textAlign: "left" }}>
                    <div style={{ fontSize: "13px", fontWeight: 700 }}>PAY WITH RAZORPAY TEST CHECKOUT</div>
                    <div style={{ fontSize: "10.5px", color: "rgba(255,255,255,0.7)" }}>
                      Order: {order.razorpay_order_id} · Signature verified by JANUS
                    </div>
                  </div>
                </div>
                <span>{busy === "checkout" ? "OPENING…" : busy === "verify" ? "VERIFYING SIGNATURE…" : "OPEN POPUP"}</span>
              </button>
            )}

            {/* Payment Verified Proof Banner */}
            {payment && (
              <div className="payment-verified-banner">
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <Check size={20} color="#10b981" />
                  <div>
                    <strong style={{ fontSize: "13px", display: "block" }}>RAZORPAY PAYMENT VERIFIED & CAPTURED</strong>
                    <span style={{ fontSize: "11px", fontFamily: "var(--font-mono)" }}>
                      Payment ID: {payment.razorpay_payment_id}
                    </span>
                  </div>
                </div>
                <StateBadge value="PAID" />
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}

/* ==========================================================================
   VIEW 6: HUMAN STEP-UP CONSOLE
   ========================================================================== */
function StepUpView({
  decision,
  data,
  order,
  resolve,
  busy,
  checkout,
  payment,
  onSimulateStepUp,
  onSimulateAdversarial,
  mandate,
}: {
  decision: Decision | null;
  data: Record<string, unknown> | null;
  order: Order | null;
  resolve: (c: "approve" | "reject") => void;
  busy: string;
  checkout: () => void;
  payment: PaymentResult | null;
  onSimulateStepUp?: () => void;
  onSimulateAdversarial?: () => void;
  mandate?: Mandate | null;
}) {
  if (!decision?.step_up_id || !data) {
    return (
      <div className="empty-box" style={{ marginTop: "60px", maxWidth: "480px", margin: "60px auto" }}>
        <UserCheck size={38} color="var(--purple-brand)" />
        <strong style={{ fontSize: "16px", marginTop: "6px" }}>Human Oversight Console</strong>
        <p style={{ color: "var(--ink-secondary)", fontSize: "12.5px", lineHeight: 1.5 }}>
          Ambiguity, missing catalog evidence, or semantic contradiction routes to this console.
          Human approve-once creates single-use authorization strictly bound to the exact proposal facts.
        </p>
        <div style={{ display: "flex", gap: "10px", marginTop: "14px", flexWrap: "wrap", justifyContent: "center" }}>
          {onSimulateStepUp && (
            <button
              className="btn-primary"
              onClick={onSimulateStepUp}
              disabled={!!busy}
            >
              <Sparkles size={14} />
              <span>Simulate Contradiction Step-Up (Demo Beat 3)</span>
            </button>
          )}
          {onSimulateAdversarial && (
            <button
              className="btn-secondary"
              style={{ color: "#b91c1c", borderColor: "#fca5a5" }}
              onClick={onSimulateAdversarial}
              disabled={!!busy}
            >
              <ShieldAlert size={14} />
              <span>Simulate Injection Step-Up (Demo Beat 5)</span>
            </button>
          )}
        </div>
      </div>
    );
  }

  const status = String(data?.status || "PENDING");
  const reasonCode = String(data?.reason_code || decision.reason_code || "SEMANTIC_CONTRADICTED");
  const proposalId = String(data?.proposal_id || decision.proposal_id || "");
  const bindingHash = String(data?.binding_hash || "");

  const evidenceObj = data?.evidence as { results?: SemanticResult[] } | undefined;
  const semanticResults: SemanticResult[] =
    decision?.semantic?.results ?? evidenceObj?.results ?? [];
  const buyerIntent =
    mandate?.instruction_text ||
    (typeof data?.instruction_text === "string" ? data.instruction_text : "Buy noise-cancelling headphones under ₹20k. Nothing flashy.");

  return (
    <>
      <div className="view-heading">
        <div>
          <p className="view-kicker">Human Oversight / 05</p>
          <h1 className="view-title">Ambiguity Belongs to Humans.</h1>
        </div>
        <p className="view-desc">
          Approve-once creates single-use authorization strictly bound to this proposal ID and exact
          catalog facts. It never mutates the original mandate.
        </p>
      </div>

      <div className="split-deck">
        <div className="deck-panel">
          <div className="panel-header">
            <span className="panel-title">ESCALATED PROPOSAL</span>
            <StateBadge value={status} />
          </div>
          <div className="contract-row">
            <span style={{ fontSize: "12px", color: "var(--ink-secondary)" }}>Reason Code</span>
            <strong style={{ fontSize: "12px", color: "#c2410c", fontFamily: "var(--font-mono)" }}>
              {pretty(reasonCode)}
            </strong>
          </div>
          <div className="contract-row">
            <span style={{ fontSize: "12px", color: "var(--ink-secondary)" }}>Proposal ID</span>
            <code style={{ fontSize: "11px", color: "var(--purple-brand)" }}>{proposalId}</code>
          </div>
          <div className="contract-row">
            <span style={{ fontSize: "12px", color: "var(--ink-secondary)" }}>Binding Hash</span>
            <code style={{ fontSize: "10px", color: "var(--ink-muted)" }}>
              {bindingHash ? `${bindingHash.slice(0, 32)}…` : "N/A"}
            </code>
          </div>

          {/* EVIDENCE-GROUNDED CITATION AUDIT CARD */}
          <div style={{ marginTop: "14px", background: "#fef2f2", border: "1px solid #fecaca", borderRadius: "8px", padding: "12px 14px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <ShieldAlert size={14} color="#dc2626" />
                <span style={{ fontSize: "11px", fontWeight: 700, fontFamily: "var(--font-mono)", color: "#991b1b", letterSpacing: "0.05em" }}>
                  EVIDENCE CITATION AUDIT
                </span>
              </div>
              <span style={{ fontSize: "10px", background: "#fee2e2", color: "#991b1b", padding: "2px 8px", borderRadius: "4px", fontWeight: 700, border: "1px solid #fca5a5" }}>
                STEP_UP TRIGGERED
              </span>
            </div>

            {buyerIntent && (
              <div style={{ fontSize: "12px", marginBottom: "8px", color: "#1e293b", background: "#ffffff", padding: "6px 10px", borderRadius: "4px", border: "1px solid #fee2e2" }}>
                <strong style={{ color: "#475569" }}>Buyer intent: </strong>
                <span>"{buyerIntent}"</span>
              </div>
            )}

            {semanticResults.length > 0 ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {semanticResults.map((sr, idx) => (
                  <div key={idx} style={{ background: "#ffffff", padding: "8px 10px", borderRadius: "6px", border: "1px solid #fecaca" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                      <span style={{ fontSize: "11.5px", fontWeight: 700, color: sr.status === "CONTRADICTED" ? "#b91c1c" : sr.status === "INSUFFICIENT_EVIDENCE" ? "#c2410c" : "#15803d" }}>
                        {sr.status}
                      </span>
                      {sr.confidence != null && (
                        <span style={{ fontSize: "10.5px", fontFamily: "var(--font-mono)", fontWeight: 600, color: sr.abstain ? "#b91c1c" : "#047857" }}>
                          {(sr.confidence * 100).toFixed(0)}% {sr.abstain ? "(Abstained)" : "Conf"}
                        </span>
                      )}
                    </div>
                    {sr.reason && (
                      <p style={{ fontSize: "11.5px", color: "#334155", margin: "2px 0 6px", lineHeight: 1.4 }}>
                        {sr.reason}
                      </p>
                    )}
                    {sr.citation && (
                      <div style={{ fontSize: "10.5px", color: "#475569", fontStyle: "italic", background: "#f8fafc", padding: "4px 8px", borderRadius: "4px", border: "1px solid #e2e8f0", marginBottom: "6px" }}>
                        "{sr.citation}"
                      </div>
                    )}
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                      {(sr.evidence || []).map((e, eIdx) => (
                        <span
                          key={eIdx}
                          style={{
                            fontSize: "10px",
                            fontFamily: "var(--font-mono)",
                            padding: "2px 6px",
                            borderRadius: "4px",
                            background: sr.status === "SUPPORTED" ? "#dcfce7" : "#fee2e2",
                            color: sr.status === "SUPPORTED" ? "#166534" : "#991b1b",
                            border: `1px solid ${sr.status === "SUPPORTED" ? "#86efac" : "#fca5a5"}`,
                            fontWeight: 500,
                          }}
                          title={e.citation || `${e.field}=${String(e.value)}`}
                        >
                          {e.field}={String(e.value)}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ fontSize: "11px", color: "#64748b" }}>
                No semantic constraints contradicted.
              </div>
            )}

            <div style={{ marginTop: "10px", padding: "6px 8px", background: "#fef2f2", borderRadius: "4px", fontSize: "11px", color: "#991b1b", fontWeight: 600, display: "flex", alignItems: "center", gap: "6px" }}>
              <ShieldAlert size={14} />
              <span>Action: STEP_UP (Autonomous purchase blocked, human escalation required)</span>
            </div>
          </div>
        </div>

        <div className="deck-panel">
          <div className="panel-header">
            <span className="panel-title">HUMAN DECISION CONSOLE</span>
            <UserCheck size={16} color="#6a3df0" />
          </div>
          <h3 style={{ fontSize: "16px", fontWeight: 800, margin: "6px 0 10px" }}>
            Accept this single exception?
          </h3>
          <p style={{ fontSize: "12px", color: "var(--ink-secondary)", lineHeight: 1.5, marginBottom: "16px" }}>
            The hard gate passed. This resolves semantic uncertainty only. All monetary and merchant
            limits remain strictly enforced.
          </p>

          {status === "PENDING" ? (
            <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
              <button className="btn-danger" onClick={() => resolve("reject")} disabled={!!busy}>
                <Ban size={14} />
                <span>REJECT</span>
              </button>
              <button className="btn-primary" onClick={() => resolve("approve")} disabled={!!busy}>
                <Check size={14} />
                <span>APPROVE ONCE</span>
              </button>
            </div>
          ) : (
            <div>
              <StateBadge value={status} />
              {order && !payment && (
                <button
                  className="btn-razorpay"
                  style={{ marginTop: "14px" }}
                  onClick={checkout}
                  disabled={!!busy}
                >
                  <span>PAY WITH RAZORPAY ({order.razorpay_order_id})</span>
                  <ArrowRight size={14} />
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

/* ==========================================================================
   VIEW 7: SIGNAL FEED (AUDIT TRAIL - Scout Style)
   ========================================================================== */
function AuditFeedView({
  events,
  refresh,
  busy,
}: {
  events: AuditEvent[];
  refresh: () => void;
  busy: string;
}) {
  const [filter, setFilter] = useState("ALL");
  const [openId, setOpenId] = useState<string | null>(null);

  const filterChips = ["ALL", "HARD_GATE", "SEMANTIC", "MANDATE", "RAZORPAY", "STEP_UP"];
  const safeEvents = Array.isArray(events) ? events : [];

  const filtered = safeEvents.filter((e) => {
    if (filter === "ALL") return true;
    return (e.event_type || "").toUpperCase().includes(filter);
  });

  return (
    <>
      <div className="view-heading">
        <div>
          <p className="view-kicker">Signal Feed / 06</p>
          <h1 className="view-title">Real-Time Decision Audit.</h1>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <button className="btn-secondary" onClick={refresh} disabled={busy === "refresh"}>
            <RefreshCw size={13} className={busy === "refresh" ? "spin" : ""} />
            <span>SYNC FEED</span>
          </button>
        </div>
      </div>

      {/* Scout-style Filter Chips */}
      <div className="feed-filter-bar">
        {filterChips.map((chip) => (
          <button
            key={chip}
            className={`filter-chip ${filter === chip ? "active" : ""}`}
            onClick={() => setFilter(chip)}
          >
            {pretty(chip)}
          </button>
        ))}
        <span style={{ marginLeft: "auto", fontSize: "11px", fontFamily: "var(--font-mono)", color: "var(--ink-muted)" }}>
          {filtered.length} SIGNALS RECORDED
        </span>
      </div>

      {/* Signal Feed Container */}
      <div className="signal-feed-container">
        <div className="signal-scroll-area">
          {filtered.map((ev, idx) => {
            const isOpen = openId === ev.id;
            return (
              <div className="signal-item-row" key={ev.id}>
                <div
                  className="signal-summary-line"
                  onClick={() => setOpenId(isOpen ? null : ev.id)}
                >
                  <span className="signal-index">#{String(filtered.length - idx).padStart(3, "0")}</span>
                  <span className="signal-time">{when(ev.created_at)}</span>
                  <span className="signal-type-tag">{pretty(ev.event_type)}</span>
                  <code style={{ fontSize: "10.5px", color: "var(--purple-brand)" }}>{ev.entity_id}</code>
                  <ChevronRight
                    size={14}
                    style={{
                      transform: isOpen ? "rotate(90deg)" : "none",
                      transition: "transform 0.15s ease",
                      color: "var(--ink-muted)",
                    }}
                  />
                </div>

                {isOpen && (
                  <pre className="signal-payload-pre">
                    {typeof ev.payload === "object" && ev.payload !== null
                      ? JSON.stringify(ev.payload, null, 2)
                      : String(ev.payload ?? "")}
                  </pre>
                )}
              </div>
            );
          })}

          {!filtered.length && (
            <div className="empty-box">
              <Clock3 size={28} />
              <strong>No Signals Found</strong>
              <p>Execute actions in the gateway to populate the cryptographic audit trail.</p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
