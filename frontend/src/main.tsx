import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { Activity, Brain, CheckCircle2, Gauge, History, Play, Settings2, Workflow } from "lucide-react";
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

type NegotiationState = {
  negotiation_id: string;
  status: string;
  config: NegotiationConfig;
  current_round: number;
  latest_offer?: Offer;
  transcript: TranscriptEntry[];
  utility_history: UtilityScore[];
  trace: TraceEvent[];
  outcome_summary?: string;
};

const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api";

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
  scenario: "Cloud GPU capacity contract for a mid-market AI platform team."
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
  loading
}: {
  config: NegotiationConfig;
  setConfig: (config: NegotiationConfig) => void;
  onStart: () => void;
  loading: boolean;
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
      <div className="run-row">
        <label className="field compact">
          <span>Max rounds</span>
          <input type="number" value={config.max_rounds} onChange={(event) => setConfig({ ...config, max_rounds: Number(event.target.value) })} />
        </label>
        <label className="field compact">
          <span>Provider</span>
          <select value={config.provider} onChange={(event) => setConfig({ ...config, provider: event.target.value })}>
            <option value="mock">mock</option>
            <option value="openai">openai</option>
            <option value="anthropic">anthropic</option>
          </select>
        </label>
        <button className="primary" onClick={onStart} disabled={loading}>
          <Play size={17} />
          {loading ? "Running" : "Start Negotiation"}
        </button>
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
  return (
    <section className="thinking-grid">
      {[["Buyer", buyer], ["Seller", seller]].map(([label, entry]) => (
        <div className="panel" key={label as string}>
          <div className="panel-heading">
            <Brain size={18} />
            <h2>{label} Visible Thinking</h2>
          </div>
          <p>{(entry as TranscriptEntry | undefined)?.visible_reasoning_summary ?? "Waiting for agent turn."}</p>
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

function App() {
  const [config, setConfig] = useState<NegotiationConfig>(defaultConfig);
  const [state, setState] = useState<NegotiationState | undefined>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | undefined>();

  const start = async () => {
    setLoading(true);
    setError(undefined);
    try {
      const response = await fetch(`${API_URL}/negotiations/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ config })
      });
      if (!response.ok) throw new Error(`API returned ${response.status}`);
      setState(await response.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const latestScore = state?.utility_history.at(-1);
  return (
    <main>
      <header className="topbar">
        <div>
          <p>Applied AI Systems Demo</p>
          <h1>Multi-Agent Negotiation Simulator</h1>
        </div>
        <div className="status-pill">{state?.status.replaceAll("_", " ") ?? "ready"}</div>
      </header>
      {error && <div className="error">Backend error: {error}</div>}
      <div className="layout">
        <ConfigPanel config={config} setConfig={setConfig} onStart={start} loading={loading} />
        <div className="main-grid">
          <OfferCard offer={state?.latest_offer} />
          <UtilityBars scores={latestScore} />
          <section className="panel outcome">
            <h2>Final Outcome</h2>
            <p>{state?.outcome_summary ?? "Run a negotiation to evaluate agreement, failure, deadlock, or walk-away."}</p>
          </section>
          <ThinkingPanels transcript={state?.transcript ?? []} />
          <HistoryPanel state={state} />
          <Transcript transcript={state?.transcript ?? []} />
          <TracePanel trace={state?.trace ?? []} />
        </div>
      </div>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
