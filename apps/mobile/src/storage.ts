import AsyncStorage from "@react-native-async-storage/async-storage";

import { DEFAULT_CATEGORIES, type NewsCategory, type UserPrefs } from "./types";

const PREFS_KEY = "newsreels.prefs";
const SAVED_KEY = "newsreels.saved";
const SEEN_KEY = "newsreels.seen";
const DEVICE_ID_KEY = "newsreels.device_id";

function generateUUID(): string {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export async function getDeviceId(): Promise<string> {
  let deviceId = await AsyncStorage.getItem(DEVICE_ID_KEY);
  if (!deviceId) {
    deviceId = generateUUID();
    await AsyncStorage.setItem(DEVICE_ID_KEY, deviceId);
  }
  return deviceId;
}

export const defaultPrefs = (deviceId: string = ""): UserPrefs => ({
  deviceId,
  state: "",
  district: "",
  categories: [...DEFAULT_CATEGORIES],
  categoryOrder: [],
  onboarded: false,
});

export async function loadPrefs(): Promise<UserPrefs> {
  const deviceId = await getDeviceId();
  const raw = await AsyncStorage.getItem(PREFS_KEY);
  if (!raw) {
    return defaultPrefs(deviceId);
  }
  try {
    const parsed = JSON.parse(raw) as UserPrefs;
    return {
      ...defaultPrefs(deviceId),
      ...parsed,
      deviceId,
      categories: parsed.categories?.length ? parsed.categories : [...DEFAULT_CATEGORIES],
      categoryOrder: parsed.categoryOrder || [],
    };
  } catch {
    return defaultPrefs(deviceId);
  }
}

export async function savePrefs(prefs: UserPrefs): Promise<void> {
  await AsyncStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
}

export async function loadSavedIds(): Promise<string[]> {
  const raw = await AsyncStorage.getItem(SAVED_KEY);
  return raw ? (JSON.parse(raw) as string[]) : [];
}

export async function toggleSaved(id: string): Promise<string[]> {
  const current = await loadSavedIds();
  const next = current.includes(id) ? current.filter((x) => x !== id) : [...current, id];
  await AsyncStorage.setItem(SAVED_KEY, JSON.stringify(next));
  return next;
}

export async function loadSeenIds(): Promise<string[]> {
  const raw = await AsyncStorage.getItem(SEEN_KEY);
  return raw ? (JSON.parse(raw) as string[]) : [];
}

export async function clearSeenIds(): Promise<void> {
  await AsyncStorage.removeItem(SEEN_KEY);
}

export async function clearAllStorage(): Promise<void> {
  await AsyncStorage.multiRemove([PREFS_KEY, SAVED_KEY, SEEN_KEY, DEVICE_ID_KEY]);
}

export async function markSeen(ids: string[]): Promise<void> {
  const current = new Set(await loadSeenIds());
  ids.forEach((id) => current.add(id));
  await AsyncStorage.setItem(SEEN_KEY, JSON.stringify([...current]));
}

export function toggleCategory(
  selected: NewsCategory[],
  chip: NewsCategory,
): NewsCategory[] {
  if (selected.includes(chip)) {
    return selected.filter((c) => c !== chip);
  }
  return [...selected, chip];
}
