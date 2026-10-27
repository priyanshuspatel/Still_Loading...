import {
  ControlAction,
  ControlSnapshot,
  controlPath,
} from './controlDeckModel';

export async function postControl(
  action: ControlAction,
  fetchFn: typeof fetch = fetch
): Promise<{ status: number; body: Record<string, unknown> }> {
  const target = controlPath(action);
  const response = await fetchFn(target.path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(target.body),
  });
  const body = (await response.json()) as Record<string, unknown>;
  return { status: response.status, body };
}

export async function fetchControlState(fetchFn: typeof fetch = fetch): Promise<ControlSnapshot> {
  const response = await fetchFn('/v1/control/state', { headers: { Accept: 'application/json' } });
  if (!response.ok) {
    throw new Error(`Control Deck responded with HTTP ${response.status}`);
  }
  return (await response.json()) as ControlSnapshot;
}
