export type NewsCategory =
  | "district"
  | "state"
  | "national"
  | "international"
  | "tech"
  | "science";

export const DEFAULT_CATEGORIES: NewsCategory[] = [
  "district",
  "state",
  "national",
  "international",
  "tech",
];

export const ALL_CATEGORIES: NewsCategory[] = [
  ...DEFAULT_CATEGORIES,
  "science",
];

export type UserPrefs = {
  deviceId?: string;
  state: string;
  district: string;
  categories: NewsCategory[];
  categoryOrder?: NewsCategory[];
  onboarded: boolean;
};

export const INDIAN_STATES: Record<string, string[]> = {
  "Andhra Pradesh": ["Visakhapatnam", "Vijayawada", "Guntur"],
  Delhi: ["New Delhi", "South Delhi", "North Delhi"],
  Karnataka: ["Bengaluru Urban", "Mysuru", "Mangaluru"],
  Maharashtra: ["Mumbai", "Pune", "Nagpur"],
  "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai"],
  Telangana: ["Hyderabad", "Warangal", "Karimnagar"],
  Kerala: ["Thiruvananthapuram", "Ernakulam", "Kozhikode"],
};
