import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { Activity, Brain, CheckCircle2, Gauge, History, KeyRound, Play, Settings2, Workflow } from "lucide-react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import "./styles.css";

type Warranty = "basic" | "standard" | "extended";
type Role = "buyer" | "seller";

type Offer = {
  price: number;
  delivery_days: number;
  warranty: Warranty;
  contract_months: number;
};

type AgentConfig = Record<string, string | number>;

type NegotiationConfig = {
  buyer: AgentConfig;
  seller: AgentConfig;
  max_rounds: number;
  provider: string;
  model_name: string;
  scenario: string;
};

type TranscriptEntry = {
  round_number: number;
  agent: Role;
  message: string;
  offer: Offer;
  visible_reasoning_summary: string;
  accept: boolean;
  walk_away: boolean;
};

type UtilityScore = { buyer: number; seller: number };
type TraceEvent = { index: number; event_type: string; detail: string; actor?: Role };
type ProviderChoice = "mock" | "openai" | "anthropic";
type ProviderSettings = {
  provider: ProviderChoice;
  apiKey: string;
  modelName: string;
};
type ProviderInfo = {
  requested_provider: string;
  active_provider: string;
  model_name: string;
  fallback_reason?: string;
  token_usage: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    approximate_cost_usd?: number;
  };
};

type NegotiationState = {
  negotiation_id: string;
  status: string;
  config: NegotiationConfig;
  current_round: number;
  latest_offer?: Offer;
  transcript: TranscriptEntry[];
  utility_history: UtilityScore[];
  trace: TraceEvent[];
  provider_info: ProviderInfo;
  outcome_summary?: string;
};

const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api";
const SETTINGS_KEY = "multi-agent-negotiation-sim.llmSettings";
const TURN_DELAY_MS = 1400;
const NEGOTIATION_TIMEOUT_MS = 90000;

const defaultConfig: NegotiationConfig = {
  buyer: {
    target_price: 82000,
    maximum_acceptable_price: 103000,
    preferred_delivery_days: 21,
    max_delivery_days: 45,
    preferred_contract_months: 12,
    risk_tolerance: 0.45,
    negotiation_style: "analytical but cooperative",
    hidden_priority: "control total cost while securing strong warranty protection"
  },
  seller: {
    target_price: 112000,
    minimum_acceptable_price: 87000,
    preferred_delivery_days: 35,
    minimum_delivery_days: 14,
    preferred_contract_months: 24,
    risk_tolerance: 0.55,
    negotiation_style: "firm, transparent, and value-oriented",
    hidden_priority: "protect margin and avoid short contracts with extended warranty"
  },
  max_rounds: 8,
  provider: "mock",
  model_name: "mock-negotiator-v1",
  scenario: "Cloud GPU capacity contract for a mid-market AI platform team."
};

const defaultSettings: ProviderSettings = {
  provider: "mock",
  apiKey: "",
  modelName: "mock-negotiator-v1"
};

const providerModels: Record<ProviderChoice, string[]> = {
  mock: ["mock-negotiator-v1"],
  openai: ["gpt-4o-mini", "gpt-4o"],
  anthropic: ["claude-3-5-haiku-latest", "claude-3-5-sonnet-latest"]
};

function Field({
  label,
  value,
  onChange,
  type = "number"
}: {
  label: string;
  value: string | number;
  type?: "number" | "text";
  onChange: (value: string | number) => void;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(type === "number" ? Number(event.target.value) : event.target.value)}
      />
    </label>
  );
}

function ConfigPanel({
  config,
  setConfig,
  onStart,
  loading,
  compatibilityWarning
}: {
  config: NegotiationConfig;
  setConfig: (config: NegotiationConfig) => void;
  onStart: () => void;
  loading: boolean;
  compatibilityWarning?: string;
}) {
  const updateAgent = (role: Role, key: string, value: string | number) => {
    setConfig({ ...config, [role]: { ...config[role], [key]: value } });
  };
  return (
    <section className="panel config-panel">
      <div className="panel-heading">
        <Settings2 size={18} />
        <h2>Agent Configuration</h2>
      </div>
      <label className="field wide">
        <span>Scenario</span>
        <input value={config.scenario} onChange={(event) => setConfig({ ...config, scenario: event.target.value })} />
      </label>
      {compatibilityWarning && <div className="config-warning">{compatibilityWarning}</div>}
      <div className="config-grid">
        <div>
          <h3>Buyer Private Config</h3>
          <Field label="Target price" value={config.buyer.target_price} onChange={(v) => updateAgent("buyer", "target_price", v)} />
          <Field label="Max price" value={config.buyer.maximum_acceptable_price} onChange={(v) => updateAgent("buyer", "maximum_acceptable_price", v)} />
          <Field label="Preferred delivery" value={config.buyer.preferred_delivery_days} onChange={(v) => updateAgent("buyer", "preferred_delivery_days", v)} />
          <Field label="Max delivery" value={config.buyer.max_delivery_days} onChange={(v) => updateAgent("buyer", "max_delivery_days", v)} />
          <Field label="Contract months" value={config.buyer.preferred_contract_months} onChange={(v) => updateAgent("buyer", "preferred_contract_months", v)} />
          <Field label="Risk tolerance" value={config.buyer.risk_tolerance} onChange={(v) => updateAgent("buyer", "risk_tolerance", v)} />
          <Field label="Style" type="text" value={config.buyer.negotiation_style} onChange={(v) => updateAgent("buyer", "negotiation_style", v)} />
          <Field label="Hidden priority" type="text" value={config.buyer.hidden_priority} onChange={(v) => updateAgent("buyer", "hidden_priority", v)} />
        </div>
        <div>
          <h3>Seller Private Config</h3>
          <Field label="Target price" value={config.seller.target_price} onChange={(v) => updateAgent("seller", "target_price", v)} />
          <Field label="Min price" value={config.seller.minimum_acceptable_price} onChange={(v) => updateAgent("seller", "minimum_acceptable_price", v)} />
          <Field label="Preferred delivery" value={config.seller.preferred_delivery_days} onChange={(v) => updateAgent("seller", "preferred_delivery_days", v)} />
          <Field label="Min delivery" value={config.seller.minimum_delivery_days} onChange={(v) => updateAgent("seller", "minimum_delivery_days", v)} />
          <Field label="Contract months" value={config.seller.preferred_contract_months} onChange={(v) => updateAgent("seller", "preferred_contract_months", v)} />
          <Field label="Risk tolerance" value={config.seller.risk_tolerance} onChange={(v) => updateAgent("seller", "risk_tolerance", v)} />
          <Field label="Style" type="text" value={config.seller.negotiation_style} onChange={(v) => updateAgent("seller", "negotiation_style", v)} />
          <Field label="Hidden priority" type="text" value={config.seller.hidden_priority} onChange={(v) => updateAgent("seller", "hidden_priority", v)} />
        </div>
      </div>
      <div className="run-row config-run-row">
        <label className="field compact">
          <span>Max rounds</span>
          <input type="number" value={config.max_rounds} onChange={(event) => setConfig({ ...config, max_rounds: Number(event.target.value) })} />
        </label>
        <button className="secondary" onClick={() => setConfig(defaultConfig)} disabled={loading} type="button">
          Reset Defaults
        </button>
        <button className="primary" onClick={onStart} disabled={loading || Boolean(compatibilityWarning)}>
          <Play size={17} />
          {loading ? "Contacting Backend" : "Start Negotiation"}
        </button>
      </div>
    </section>
  );
}

function SettingsPanel({
  settings,
  setSettings,
  activeInfo
}: {
  settings: ProviderSettings;
  setSettings: (settings: ProviderSettings) => void;
  activeInfo?: ProviderInfo;
}) {
  const update = (next: ProviderSettings) => {
    setSettings(next);
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(next));
  };
  const setProvider = (provider: ProviderChoice) => {
    update({
      provider,
      apiKey: provider === settings.provider ? settings.apiKey : "",
      modelName: providerModels[provider][0]
    });
  };
  return (
    <section className="panel settings-panel">
      <div className="panel-heading">
        <KeyRound size={18} />
        <h2>LLM Settings</h2>
      </div>
      <div className="segmented">
        {[
          ["mock", "Mock Mode"],
          ["openai", "OpenAI"],
          ["anthropic", "Anthropic"]
        ].map(([value, label]) => (
          <button
            key={value}
            className={settings.provider === value ? "selected" : ""}
            onClick={() => setProvider(value as ProviderChoice)}
            type="button"
          >
            {label}
          </button>
        ))}
      </div>
      <label className="field">
        <span>Model name</span>
        <input
          list="model-options"
          value={settings.modelName}
          onChange={(event) => update({ ...settings, modelName: event.target.value })}
        />
        <datalist id="model-options">
          {providerModels[settings.provider].map((model) => <option value={model} key={model} />)}
        </datalist>
      </label>
      <label className="field">
        <span>API key</span>
        <input
          type="password"
          autoComplete="off"
          placeholder={settings.provider === "mock" ? "Not required for mock mode" : "Stored only in this browser"}
          disabled={settings.provider === "mock"}
          value={settings.apiKey}
          onChange={(event) => update({ ...settings, apiKey: event.target.value })}
        />
      </label>
      <p className="settings-note">
        Keys are saved only in browser localStorage and sent as temporary request headers.
      </p>
      <div className="active-provider">
        <span>Active</span>
        <b>{activeInfo ? `${activeInfo.active_provider} / ${activeInfo.model_name}` : `${settings.provider} / ${settings.modelName}`}</b>
        {activeInfo?.fallback_reason && <p>{activeInfo.fallback_reason}</p>}
      </div>
    </section>
  );
}

function OfferCard({ offer }: { offer?: Offer }) {
  return (
    <section className="panel offer-card">
      <div className="panel-heading">
        <CheckCircle2 size={18} />
        <h2>Current Offer</h2>
      </div>
      {offer ? (
        <div className="offer-grid">
          <strong>${offer.price.toLocaleString()}</strong>
          <span>{offer.delivery_days} days</span>
          <span>{offer.warranty} warranty</span>
          <span>{offer.contract_months} months</span>
        </div>
      ) : (
        <p className="muted">No active offer yet.</p>
      )}
    </section>
  );
}

function UtilityBars({ scores }: { scores?: UtilityScore }) {
  const buyer = scores?.buyer ?? 0;
  const seller = scores?.seller ?? 0;
  return (
    <section className="panel">
      <div className="panel-heading">
        <Gauge size={18} />
        <h2>Utility Scores</h2>
      </div>
      <div className="bar-row"><span>Buyer</span><div><i style={{ width: `${buyer}%` }} /></div><b>{buyer}</b></div>
      <div className="bar-row seller"><span>Seller</span><div><i style={{ width: `${seller}%` }} /></div><b>{seller}</b></div>
    </section>
  );
}

function ThinkingPanels({ transcript }: { transcript: TranscriptEntry[] }) {
  const buyer = [...transcript].reverse().find((entry) => entry.agent === "buyer");
  const seller = [...transcript].reverse().find((entry) => entry.agent === "seller");
  const summaries: Array<[string, TranscriptEntry | undefined]> = [["Buyer", buyer], ["Seller", seller]];
  return (
    <section className="thinking-grid">
      {summaries.map(([label, entry]) => (
        <div className="panel" key={label}>
          <div className="panel-heading">
            <Brain size={18} />
            <h2>{label} Visible Thinking</h2>
          </div>
          <p>{entry?.visible_reasoning_summary ?? "Waiting for agent turn."}</p>
        </div>
      ))}
    </section>
  );
}

function Transcript({ transcript }: { transcript: TranscriptEntry[] }) {
  return (
    <section className="panel transcript">
      <div className="panel-heading">
        <Activity size={18} />
        <h2>Round Transcript</h2>
      </div>
      {transcript.length === 0 ? <p className="muted">Start the run to see structured agent messages.</p> : transcript.map((entry) => (
        <article className={`turn ${entry.agent}`} key={`${entry.round_number}-${entry.agent}`}>
          <header>
            <b>Round {entry.round_number}: {entry.agent}</b>
            <span>{entry.accept ? "Accepted" : entry.walk_away ? "Walked away" : "Counteroffer"}</span>
          </header>
          <p>{entry.message}</p>
          <div className="reasoning-callout">
            <b>Visible thinking</b>
            <span>{entry.visible_reasoning_summary}</span>
          </div>
          <code>{JSON.stringify(entry.offer)}</code>
        </article>
      ))}
    </section>
  );
}

function HistoryPanel({ state }: { state?: NegotiationState }) {
  const chartData = useMemo(() => state?.transcript.map((entry, index) => ({
    round: entry.round_number,
    price: entry.offer.price,
    buyer: state.utility_history[index]?.buyer ?? 0,
    seller: state.utility_history[index]?.seller ?? 0
  })) ?? [], [state]);
  return (
    <section className="panel history-panel">
      <div className="panel-heading">
        <History size={18} />
        <h2>Offer History</h2>
      </div>
      {chartData.length ? (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="round" />
            <YAxis yAxisId="left" />
            <YAxis yAxisId="right" orientation="right" domain={[0, 100]} />
            <Tooltip />
            <Legend />
            <Line yAxisId="left" type="monotone" dataKey="price" stroke="#0f766e" strokeWidth={2} />
            <Line yAxisId="right" type="monotone" dataKey="buyer" stroke="#2563eb" strokeWidth={2} />
            <Line yAxisId="right" type="monotone" dataKey="seller" stroke="#b45309" strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      ) : <p className="muted">No offers recorded.</p>}
    </section>
  );
}

function TracePanel({ trace }: { trace: TraceEvent[] }) {
  return (
    <section className="panel trace">
      <div className="panel-heading">
        <Workflow size={18} />
        <h2>Orchestration Trace</h2>
      </div>
      {trace.map((event) => (
        <div className="trace-row" key={event.index}>
          <span>{event.index}</span>
          <b>{event.event_type.replaceAll("_", " ")}</b>
          <p>{event.actor ? `${event.actor}: ` : ""}{event.detail}</p>
        </div>
      ))}
    </section>
  );
}

function ProviderUsagePanel({ info }: { info?: ProviderInfo }) {
  const usage = info?.token_usage;
  return (
    <section className="panel provider-panel">
      <h2>Provider & Cost</h2>
      <div className="provider-metrics">
        <div><span>Requested</span><b>{info?.requested_provider ?? "mock"}</b></div>
        <div><span>Active</span><b>{info?.active_provider ?? "mock"}</b></div>
        <div><span>Model</span><b>{info?.model_name ?? "mock-negotiator-v1"}</b></div>
        <div><span>Tokens</span><b>{usage?.total_tokens ?? 0}</b></div>
        <div><span>Approx. cost</span><b>{usage?.approximate_cost_usd == null ? "n/a" : `$${usage.approximate_cost_usd.toFixed(6)}`}</b></div>
      </div>
    </section>
  );
}

function LiveStepPanel({
  isReplaying,
  visibleTurns,
  totalTurns,
  latestTurn
}: {
  isReplaying: boolean;
  visibleTurns: number;
  totalTurns: number;
  latestTurn?: TranscriptEntry;
}) {
  return (
    <section className="panel live-step">
      <h2>Live Step</h2>
      <div className={isReplaying ? "pulse-line active" : "pulse-line"} />
      <p>
        {isReplaying
          ? `Revealing turn ${visibleTurns} of ${totalTurns}.`
          : totalTurns
            ? "Negotiation playback complete."
            : "Start a negotiation to watch each agent turn."}
      </p>
      {latestTurn && (
        <div className="live-turn">
          <b>{latestTurn.agent} offer rationale</b>
          <span>{latestTurn.visible_reasoning_summary}</span>
        </div>
      )}
    </section>
  );
}

function App() {
  const [config, setConfig] = useState<NegotiationConfig>(defaultConfig);
  const [settings, setSettings] = useState<ProviderSettings>(defaultSettings);
  const [state, setState] = useState<NegotiationState | undefined>();
  const [visibleTurns, setVisibleTurns] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | undefined>();

  useEffect(() => {
    const saved = localStorage.getItem(SETTINGS_KEY);
    if (saved) {
      setSettings({ ...defaultSettings, ...JSON.parse(saved) });
    }
  }, []);

  useEffect(() => {
    if (!state) return;
    setVisibleTurns(0);
    const totalTurns = state.transcript.length;
    let nextTurn = 0;
    const timer = window.setInterval(() => {
      nextTurn += 1;
      setVisibleTurns(Math.min(nextTurn, totalTurns));
      if (nextTurn >= totalTurns) {
        window.clearInterval(timer);
      }
    }, TURN_DELAY_MS);
    return () => window.clearInterval(timer);
  }, [state?.negotiation_id]);

  const start = async () => {
    if (compatibilityWarning) {
      setError(compatibilityWarning);
      return;
    }
    setLoading(true);
    setError(undefined);
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), NEGOTIATION_TIMEOUT_MS);
    const provider = settings.provider;
    const effectiveProvider = provider !== "mock" && !settings.apiKey ? "mock" : provider;
    const effectiveConfig = {
      ...config,
      provider: effectiveProvider,
      model_name: provider === effectiveProvider ? settings.modelName : "mock-negotiator-v1"
    };
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "X-LLM-Provider": provider,
      "X-LLM-Model": settings.modelName
    };
    if (settings.apiKey) {
      headers["X-LLM-API-Key"] = settings.apiKey;
    }
    try {
      const response = await fetch(`${API_URL}/negotiations/start`, {
        method: "POST",
        headers,
        body: JSON.stringify({ config: effectiveConfig }),
        signal: controller.signal
      });
      if (!response.ok) throw new Error(`API returned ${response.status}`);
      const completedState = await response.json();
      setState(completedState);
    } catch (err) {
      const message = err instanceof Error && err.name === "AbortError"
        ? `Timed out waiting for ${API_URL}. If this is Render, the backend may be waking up or VITE_API_URL may point to the wrong service URL.`
        : err instanceof Error
          ? `${err.message}. API endpoint: ${API_URL}`
          : `Unknown error. API endpoint: ${API_URL}`;
      setError(message);
    } finally {
      window.clearTimeout(timeout);
      setLoading(false);
    }
  };

  const visibleTranscript = state?.transcript.slice(0, visibleTurns) ?? [];
  const visibleUtilities = state?.utility_history.slice(0, visibleTurns) ?? [];
  const visibleTrace = state?.trace.filter((event) => event.event_type === "provider_fallback" || event.index <= visibleTurns * 5 + 1) ?? [];
  const latestTurn = visibleTranscript[visibleTranscript.length - 1];
  const latestScore = visibleUtilities[visibleUtilities.length - 1];
  const isReplaying = Boolean(state && visibleTurns < state.transcript.length);
  const visibleStatus = isReplaying ? `playing ${visibleTurns}/${state?.transcript.length ?? 0}` : state?.status.replaceAll("_", " ") ?? "ready";
  const visibleState = state
    ? {
        ...state,
        status: visibleStatus,
        transcript: visibleTranscript,
        utility_history: visibleUtilities,
        trace: visibleTrace,
        latest_offer: latestTurn?.offer,
        outcome_summary: isReplaying ? undefined : state.outcome_summary
      }
    : undefined;
  const compatibilityWarning = getCompatibilityWarning(config);
  return (
    <main>
      <header className="topbar">
        <div>
          <p>Applied AI Systems Demo</p>
          <h1>Multi-Agent Negotiation Simulator</h1>
        </div>
        <div className="status-pill">{visibleStatus}</div>
      </header>
      {error && <div className="error">Backend error: {error}</div>}
      <div className="layout">
        <aside className="side-stack">
          <SettingsPanel settings={settings} setSettings={setSettings} activeInfo={state?.provider_info} />
          <ConfigPanel
            config={config}
            setConfig={setConfig}
            onStart={start}
            loading={loading}
            compatibilityWarning={compatibilityWarning}
          />
        </aside>
        <div className="main-grid">
          <OfferCard offer={visibleState?.latest_offer} />
          <UtilityBars scores={latestScore} />
          <LiveStepPanel
            isReplaying={isReplaying}
            visibleTurns={visibleTurns}
            totalTurns={state?.transcript.length ?? 0}
            latestTurn={latestTurn}
          />
          <ProviderUsagePanel info={state?.provider_info} />
          <section className="panel outcome">
            <h2>Final Outcome</h2>
            <p>{visibleState?.outcome_summary ?? "Run a negotiation to evaluate agreement, failure, deadlock, or walk-away."}</p>
          </section>
          <ThinkingPanels transcript={visibleTranscript} />
          <HistoryPanel state={visibleState} />
          <Transcript transcript={visibleTranscript} />
          <TracePanel trace={visibleTrace} />
        </div>
      </div>
    </main>
  );
}

function getCompatibilityWarning(config: NegotiationConfig): string | undefined {
  const buyerMaxPrice = Number(config.buyer.maximum_acceptable_price);
  const sellerMinPrice = Number(config.seller.minimum_acceptable_price);
  if (sellerMinPrice > buyerMaxPrice) {
    return `No feasible price range: seller minimum price ($${sellerMinPrice.toLocaleString()}) is above buyer maximum price ($${buyerMaxPrice.toLocaleString()}). Lower seller minimum or raise buyer maximum.`;
  }
  const buyerMaxDelivery = Number(config.buyer.max_delivery_days);
  const sellerMinDelivery = Number(config.seller.minimum_delivery_days);
  if (sellerMinDelivery > buyerMaxDelivery) {
    return `No feasible delivery range: seller minimum delivery (${sellerMinDelivery} days) is above buyer maximum delivery (${buyerMaxDelivery} days).`;
  }
  return undefined;
}

createRoot(document.getElementById("root")!).render(<App />);
