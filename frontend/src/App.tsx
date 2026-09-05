import { type ReactNode, useCallback, useEffect, useState } from "react";
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
  evidence: { field: string; value: unknown; source: string }[];
  reason: string;
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
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body?.detail?.reason_code ?? body?.detail?.message ?? `HTTP ${response.status}`);
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

const pretty = (value: string) => value.replaceAll("_", " ");

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
  const [merchantId, setMerchantId] = useState(import.meta.env.VITE_MERCHANT_ID ?? "northstar_audio");

  const refresh = useCallback(async () => {
    const catalogPath = merchantId
      ? `/api/v1/products?merchant_id=${encodeURIComponent(merchantId)}`
      : "/api/v1/products";
    const [catalog, events] = await Promise.all([
      request<Product[]>(catalogPath).catch(() => []),
      request<AuditEvent[]>("/api/v1/audit?limit=100").catch(() => []),
    ]);
    setProducts(catalog);
    setAudit(events);
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

  return (
    <div className="window-shell">
      {/* Top Scout-Style Announcement Banner */}
      <div className="announcement-bar">
        <span className="announcement-badge">Live Gateway</span>
        <span>Deterministic Hard Gate · Semantic Intent Path · Razorpay Test-Mode Integration</span>
      </div>

      {/* Mac Window Mockup Header */}
      <div className="browser-header">
        <div className="traffic-lights">
          <div className="dot dot-red" />
          <div className="dot dot-yellow" />
          <div className="dot dot-green" />
        </div>
        <div className="browser-address">
          <LockKeyhole size={11} />
          <span>https://app.janus.gateway/live-console</span>
        </div>
        <div className="header-status">
          <div className="status-pill-live">
            <span className="live-pulse" />
            <span>ONLINE</span>
          </div>
        </div>
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
            {view === "overview" && (
              <OverviewView
                products={products}
                events={audit}
                mandate={mandate}
                go={setView}
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
              />
            )}

            {view === "audit" && (
              <AuditFeedView
                events={audit}
                refresh={() => act("refresh", refresh)}
                busy={busy}
              />
            )}
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
  go,
}: {
  products: Product[];
  events: AuditEvent[];
  mandate: Mandate | null;
  go: (v: View) => void;
}) {
  const pipelineSteps = [
    { num: "01", title: "Signed Mandate", desc: "Human-bounded intent signed with ECDSA P-256", icon: Fingerprint },
    { num: "02", title: "Hard Gate", desc: "Deterministic checks on amount, currency, merchant", icon: ShieldCheck },
    { num: "03", title: "Semantic Intent", desc: "Catalog-authoritative evidence classifier", icon: Sparkles },
    { num: "04", title: "Razorpay Exec", desc: "Atomic reservation + hosted test-mode checkout", icon: ShoppingBag },
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

      {/* 4-Node Authority Pipeline */}
      <div className="authority-flow">
        {pipelineSteps.map((step) => {
          const Icon = step.icon;
          return (
            <div className="flow-card" key={step.num}>
              <div className="flow-top">
                <span className="flow-step-num">{step.num}</span>
                <div className="flow-icon-box">
                  <Icon size={17} />
                </div>
              </div>
              <span className="flow-title">{step.title}</span>
              <p className="flow-desc">{step.desc}</p>
            </div>
          );
        })}
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
          <span className="metric-header">DECISION ACCURACY</span>
          <span className="metric-number">100%</span>
          <span className="metric-caption">zero unauthorized bypass</span>
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
}: {
  products: Product[];
  merchantId: string;
  setMerchantId: (v: string) => void;
  refresh: () => Promise<void>;
  busy: string;
  act: (label: string, fn: () => Promise<void>) => Promise<void>;
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
            <label className="form-label" htmlFor="catalog-json-textarea">Or Paste JSON Records</label>
            <textarea
              id="catalog-json-textarea"
              className="form-textarea"
              value={payload}
              onChange={(e) => setPayload(e.target.value)}
              placeholder='[{"id":"sku-001","merchant_id":"northstar_audio","name":"Headphones","price_paise":1849900,"currency":"INR","category":"headphones","condition":"new","active":true,"attributes":{"color":"black"}}]'
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
            <span className="panel-title">LIVE CATALOG ({products.length} SKUs)</span>
            <span style={{ fontSize: "11px", fontFamily: "var(--font-mono)", color: "var(--ink-muted)" }}>
              MERCHANT: {merchantId}
            </span>
          </div>

          <div className="catalog-list-scroll">
            {products.map((p) => (
              <div className="product-row-item" key={p.id}>
                <div className="prod-meta">
                  <span className="prod-name">{p.name}</span>
                  <div className="prod-tags">
                    <span className="attr-tag">{p.id}</span>
                    <span className="attr-tag">{p.category}</span>
                    <span className="attr-tag">{p.condition}</span>
                    {Object.entries(p.attributes || {}).map(([k, v]) => (
                      <span className="attr-tag" key={k}>
                        {k}: {String(v)}
                      </span>
                    ))}
                  </div>
                </div>
                <span className="prod-price">{money(p.price_paise)}</span>
                <StateBadge value={p.active ? "ACTIVE" : "INACTIVE"} />
              </div>
            ))}

            {!products.length && (
              <div className="empty-box">
                <ShoppingBag size={28} />
                <strong>Catalog is Empty</strong>
                <p>Import merchant products to establish authoritative catalog facts.</p>
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
}) {
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

      {!mandate ? (
        <div className="empty-box" style={{ marginTop: "80px" }}>
          <ShoppingBag size={32} />
          <strong>No Active Authority</strong>
          <p>You must issue an active mandate before an agent can propose purchases.</p>
        </div>
      ) : (
        <div className="simulator-layout">
          {/* Left Column: Product Selection */}
          <div className="simulator-catalog-column">
            <div className="panel-header" style={{ padding: "14px 16px" }}>
              <span className="panel-title">SELECT SKU TO PROPOSE</span>
              <span style={{ fontSize: "10px", fontFamily: "var(--font-mono)", color: "var(--ink-muted)" }}>
                CATALOG BOUND
              </span>
            </div>

            <div style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
              {products.map((p) => {
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
                    DETERMINISTIC HARD GATE ({decision.hard_gate.checks.length} CHECKS)
                  </span>
                  <div className="checks-grid">
                    {decision.hard_gate.checks.map((chk) => (
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
                    {decision.semantic.results.map((item) => (
                      <div key={item.constraint_id} style={{ marginTop: "6px" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <strong style={{ fontSize: "12px" }}>{pretty(item.constraint_id)}</strong>
                          <StateBadge value={item.status} />
                        </div>
                        <p style={{ fontSize: "11.5px", color: "var(--ink-secondary)", margin: "3px 0" }}>{item.reason}</p>
                        <span style={{ fontSize: "10px", fontFamily: "var(--font-mono)", color: "var(--purple-brand)" }}>
                          Evidence: {item.evidence.map((e) => `${e.field}: ${String(e.value)}`).join(" · ") || "None"}
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
}: {
  decision: Decision | null;
  data: Record<string, unknown> | null;
  order: Order | null;
  resolve: (c: "approve" | "reject") => void;
  busy: string;
  checkout: () => void;
  payment: PaymentResult | null;
}) {
  if (!decision?.step_up_id || !data) {
    return (
      <div className="empty-box" style={{ marginTop: "80px" }}>
        <UserCheck size={32} />
        <strong>No Escalation Pending</strong>
        <p>Ambiguity, missing evidence, or contradiction routes to human decision here.</p>
      </div>
    );
  }

  const status = String(data.status);

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
              {pretty(String(data.reason_code))}
            </strong>
          </div>
          <div className="contract-row">
            <span style={{ fontSize: "12px", color: "var(--ink-secondary)" }}>Proposal ID</span>
            <code style={{ fontSize: "11px", color: "var(--purple-brand)" }}>{String(data.proposal_id)}</code>
          </div>
          <div className="contract-row">
            <span style={{ fontSize: "12px", color: "var(--ink-secondary)" }}>Binding Hash</span>
            <code style={{ fontSize: "10px", color: "var(--ink-muted)" }}>
              {String(data.binding_hash).slice(0, 32)}…
            </code>
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

  const filtered = events.filter((e) => {
    if (filter === "ALL") return true;
    return e.event_type.toUpperCase().includes(filter);
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
                    {JSON.stringify(ev.payload, null, 2)}
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
