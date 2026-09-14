export type CardSource = {
  source_id: string;
  name: string;
  url: string;
  trust_tier: number | string;
};

export type FeedCard = {
  id: string;
  headline: string;
  summary: string;
  category: string;
  verified_status: string;
  verification_type?: "cross_verified" | "official_source" | "flagged_conflict" | null;
  created_at: string | null;
  published_at: string | null;
  district: string | null;
  state: string | null;
  image_url?: string | null;
  image_author?: string | null;
  image_author_url?: string | null;
  priority_score: number;
  sources: CardSource[];
};

export function getApiBaseUrl(): string {
  if (process.env.EXPO_PUBLIC_API_URL) {
    return process.env.EXPO_PUBLIC_API_URL;
  }
  if (typeof window !== "undefined" && window.location?.hostname) {
    return `http://${window.location.hostname}:8000`;
  }
  return "http://127.0.0.1:8000";
}

export async function reverseGeocode(latitude: number, longitude: number): Promise<{
  district: string | null;
  state: string | null;
  display_name: string | null;
}> {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}/location/reverse?latitude=${encodeURIComponent(latitude)}&longitude=${encodeURIComponent(longitude)}`;
  try {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Location lookup failed: HTTP ${response.status}`);
    }
    const data = await response.json();
    return data;
  } catch (err) {
    console.error("Reverse geocoding error:", err);
    throw err;
  }
}

export async function fetchFeed(params: {
  categories: string[];
  district?: string;
  state?: string;
  deviceId?: string;
  limit?: number;
  offset?: number;
}): Promise<{
  items: FeedCard[];
  fallbackUsed: boolean;
  fallbackLevel: string | null;
  emptyReason: string | null;
}> {
  const query = new URLSearchParams();
  const validCats = params.categories.filter((c) => c && c.toLowerCase() !== "all" && c.toLowerCase() !== "global");
  if (validCats.length) {
    query.set("categories", validCats.join(","));
  }
  if (params.district) {
    query.set("district", params.district);
  }
  if (params.state) {
    query.set("state", params.state);
  }
  if (params.deviceId) {
    query.set("device_id", params.deviceId);
  }
  query.set("limit", String(params.limit ?? 100));
  if (params.offset) {
    query.set("offset", String(params.offset));
  }

  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}/feed?${query.toString()}`;

  let response: Response;
  try {
    response = await fetch(url);
  } catch (err: any) {
    throw new Error(
      `Network error connecting to API (${url}): ${err?.message || "Failed to fetch"}. Ensure FastAPI is active on port 8000.`
    );
  }

  if (!response.ok) {
    const errorBody = await response.text().catch(() => "");
    throw new Error(`Feed API error HTTP ${response.status} (${response.statusText}): ${errorBody || "Unknown error"}`);
  }

  const body = (await response.json()) as {
    items: FeedCard[];
    fallback_used: boolean;
    fallback_level: string | null;
    empty_reason: string | null;
  };
  return {
    items: body.items ?? [],
    fallbackUsed: body.fallback_used ?? false,
    fallbackLevel: body.fallback_level ?? null,
    emptyReason: body.empty_reason ?? null,
  };
}

export async function updateUserPreferences(
  deviceId: string,
  categoryOrder: string[]
): Promise<{ device_id: string; category_order: string[] }> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/user/${deviceId}/preferences`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ category_order: categoryOrder }),
  });
  if (!response.ok) {
    throw new Error(`update preferences failed: HTTP ${response.status}`);
  }
  return response.json();
}

export async function getUserPreferences(
  deviceId: string
): Promise<{ device_id: string; category_order: string[] }> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/user/${deviceId}/preferences`);
  if (!response.ok) {
    throw new Error(`get preferences failed: HTTP ${response.status}`);
  }
  return response.json();
}
