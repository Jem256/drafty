export interface Example {
  id: string;
  title: string;
  brief: string;
  note: string;
}

export interface Check {
  rule_id: string;
  element_id: string;
  status: string;
  measured: unknown;
  limit: unknown;
  message: string;
}

export interface RunState {
  run_id: string;
  state: string;
  brief: string | null;
  message: string | null;
  questions: string[];
  spec: Record<string, unknown> | null;
  results: { warnings?: string[] } | null;
  checks: Check[];
  outputs: Record<string, string>;
}

async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return body.detail ?? `request failed (${response.status})`;
  } catch {
    return `request failed (${response.status})`;
  }
}

export async function getExamples(): Promise<Example[]> {
  const response = await fetch("/api/examples");
  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()).examples;
}

export async function startRun(brief: string): Promise<string> {
  const response = await fetch("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ brief }),
  });
  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()).run_id;
}

export async function getRun(runId: string): Promise<RunState> {
  const response = await fetch(`/api/runs/${runId}`);
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

export async function submitAnswers(
  runId: string,
  answers: Record<string, string>,
): Promise<void> {
  const response = await fetch(`/api/runs/${runId}/answers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answers }),
  });
  if (!response.ok) throw new Error(await readError(response));
}

export function eventsUrl(runId: string): string {
  return `/api/runs/${runId}/events`;
}

export function fileUrl(runId: string, name: string): string {
  return `/api/runs/${runId}/files/${name}`;
}

export async function getText(runId: string, name: string): Promise<string> {
  const response = await fetch(fileUrl(runId, name));
  if (!response.ok) throw new Error(await readError(response));
  return response.text();
}

export async function getJson<T>(runId: string, name: string): Promise<T> {
  const response = await fetch(fileUrl(runId, name));
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}
