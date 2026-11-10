export interface Stats {
  boxes: number;
  items: number;
  units: number;
  locations: number;
}

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function fetchStats(): Promise<Stats> {
  const response = await fetch(`${API_URL}/api/stats`);
  if (!response.ok) {
    throw new Error(`API ${API_URL} вернул статус ${response.status}`);
  }
  return (await response.json()) as Stats;
}
