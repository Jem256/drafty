import { useCallback, useEffect, useRef, useState } from "react";
import {
  type Example,
  type RunState,
  eventsUrl,
  fileUrl,
  getExamples,
  getJson,
  getRun,
  getText,
  startRun,
  submitAnswers,
} from "./api";

const EVENT_TYPES = [
  "state",
  "model_call",
  "tool_call",
  "checks",
  "question",
  "done",
  "escalated",
  "error",
];

const TERMINAL = new Set(["done", "escalated", "error"]);

interface LogEntry {
  seq: number;
  type: string;
  text: string;
}

interface TraceData {
  seq: number;
  state?: string;
  role?: string;
  model?: string;
  checks_summary?: { pass?: number; fail?: number; warn?: number };
}

function summarise(type: string, data: TraceData): string {
  switch (type) {
    case "state":
      return `state: ${data.state ?? ""}`;
    case "model_call":
      return `model call: ${data.role ?? ""} on ${data.model ?? ""}`;
    case "checks": {
      const summary = data.checks_summary ?? {};
      return `checks: ${summary.pass ?? 0} pass, ${summary.fail ?? 0} fail, ${summary.warn ?? 0} warn`;
    }
    case "question":
      return "waiting for your answers";
    case "done":
      return "done";
    case "escalated":
      return "escalated to the engineer";
    case "error":
      return "run failed";
    default:
      return type;
  }
}

export default function App() {
  const [examples, setExamples] = useState<Example[]>([]);
  const [brief, setBrief] = useState("");
  const [runId, setRunId] = useState<string | null>(null);
  const [run, setRun] = useState<RunState | null>(null);
  const [log, setLog] = useState<LogEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [schedule, setSchedule] = useState<string[][]>([]);
  const [quantities, setQuantities] = useState<Record<string, number> | null>(null);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    getExamples()
      .then(setExamples)
      .catch(() => undefined);
    return () => sourceRef.current?.close();
  }, []);

  const refresh = useCallback(async (id: string) => {
    const state = await getRun(id);
    setRun(state);
    if (state.state === "done" || state.state === "escalated") {
      const csv = await getText(id, "schedule.csv").catch(() => "");
      setSchedule(
        csv
          ? csv
              .trim()
              .split("\n")
              .map((line) => line.split(","))
          : [],
      );
      setQuantities(await getJson<Record<string, number>>(id, "quantities.json").catch(() => null));
    }
  }, []);

  const subscribe = useCallback(
    (id: string) => {
      sourceRef.current?.close();
      const source = new EventSource(eventsUrl(id));
      sourceRef.current = source;
      EVENT_TYPES.forEach((type) => {
        source.addEventListener(type, (event) => {
          const data = JSON.parse((event as MessageEvent).data) as TraceData;
          setLog((previous) => [...previous, { seq: data.seq, type, text: summarise(type, data) }]);
          if (TERMINAL.has(type) || type === "question") {
            void refresh(id);
          }
          if (TERMINAL.has(type)) {
            source.close();
          }
        });
      });
    },
    [refresh],
  );

  const onSubmit = async () => {
    setError(null);
    setLog([]);
    setRun(null);
    setSchedule([]);
    setQuantities(null);
    setAnswers({});
    try {
      const id = await startRun(brief);
      setRunId(id);
      subscribe(id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  };

  const onAnswer = async () => {
    if (!runId) return;
    try {
      await submitAnswers(runId, answers);
      setAnswers({});
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  };

  const warnings = run?.results?.warnings ?? [];
  const showResults = run && (run.state === "done" || run.state === "escalated");

  return (
    <main className="app">
      <header className="header">
        <h1>Drafty</h1>
        <p className="tagline">
          Describe the road, get a drainage layout that has already been checked and fixed against
          engineering rules, with the reasoning shown.
        </p>
      </header>

      <div className="disclaimer" role="note">
        First draft for engineer review. Not a certified design. Do not build from these outputs
        without a qualified engineer.
      </div>

      <section className="card">
        <label className="field-label" htmlFor="brief">
          Road brief
        </label>
        <textarea
          id="brief"
          value={brief}
          onChange={(event) => setBrief(event.target.value)}
          rows={6}
          placeholder="Describe the road, its falls, the drains and any culverts…"
        />
        <div className="examples">
          {examples.map((example) => (
            <button
              key={example.id}
              type="button"
              className="example"
              onClick={() => setBrief(example.brief)}
              title={example.note}
            >
              {example.title}
            </button>
          ))}
        </div>
        <button type="button" className="primary" onClick={onSubmit} disabled={!brief.trim()}>
          Draft the design
        </button>
      </section>

      {error && <div className="error">{error}</div>}

      {warnings.length > 0 && (
        <div className="warning" role="alert">
          <strong>Warnings:</strong>
          <ul>
            {warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      {log.length > 0 && (
        <section className="card">
          <h2>Live log</h2>
          <ol className="log">
            {log.map((entry) => (
              <li key={entry.seq} className={`log-${entry.type}`}>
                {entry.text}
              </li>
            ))}
          </ol>
        </section>
      )}

      {run?.state === "awaiting_answers" && (
        <section className="card question">
          <h2>I need a few answers</h2>
          {run.questions.map((question) => (
            <div key={question} className="field">
              <label htmlFor={question}>{question}</label>
              <input
                id={question}
                value={answers[question] ?? ""}
                onChange={(event) =>
                  setAnswers((previous) => ({ ...previous, [question]: event.target.value }))
                }
              />
            </div>
          ))}
          <button type="button" className="primary" onClick={onAnswer}>
            Send answers
          </button>
        </section>
      )}

      {showResults && runId && (
        <>
          <section className="card">
            <h2>Drawing</h2>
            <img className="preview" src={fileUrl(runId, "preview.svg")} alt="Drainage layout" />
            <div className="downloads">
              <a href={fileUrl(runId, "drawing.dxf")}>DXF</a>
              <a href={fileUrl(runId, "schedule.csv")}>Schedule (CSV)</a>
              <a href={fileUrl(runId, "quantities.json")}>Quantities (JSON)</a>
            </div>
          </section>

          <section className="card">
            <h2>Checks</h2>
            <table>
              <thead>
                <tr>
                  <th>Rule</th>
                  <th>Element</th>
                  <th>Status</th>
                  <th>Message</th>
                </tr>
              </thead>
              <tbody>
                {run.checks.map((check) => (
                  <tr key={`${check.rule_id}-${check.element_id}`} className={`status-${check.status}`}>
                    <td>{check.rule_id}</td>
                    <td>{check.element_id}</td>
                    <td>{check.status}</td>
                    <td>{check.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          {schedule.length > 1 && (
            <section className="card">
              <h2>Drain schedule</h2>
              <table>
                <thead>
                  <tr>
                    {schedule[0].map((header) => (
                      <th key={header}>{header}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {schedule.slice(1).map((row, index) => (
                    <tr key={index}>
                      {row.map((cell, cellIndex) => (
                        <td key={cellIndex}>{cell}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          {quantities && (
            <section className="card">
              <h2>Rough quantities</h2>
              <ul className="quantities">
                {Object.entries(quantities).map(([key, value]) => (
                  <li key={key}>
                    <span>{key.replace(/_/g, " ")}</span>
                    <strong>{typeof value === "number" ? value.toFixed(1) : value}</strong>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section className="card">
            <h2>Why this design</h2>
            <p className="rationale">{run.message}</p>
          </section>
        </>
      )}

      <footer className="footer">
        Drafty uses NVIDIA Nemotron models on Nebius Token Factory. Every number is computed by the
        engine, never by the model.
      </footer>
    </main>
  );
}
