export type NewsCategory =
  | "state"
  | "national"
  | "international"
  | "tech"
  | "science"
  | "politics"
  | "business"
  | "health"
  | "sports"
  | "education";

export const ALL_CATEGORIES: NewsCategory[] = [
  "state",
  "national",
  "international",
  "tech",
  "science",
  "politics",
  "business",
  "health",
  "sports",
  "education",
];

export const DEFAULT_CATEGORIES: NewsCategory[] = [...ALL_CATEGORIES];

export type UserPrefs = {
  deviceId?: string;
  state: string;
  district?: string;
  categories: NewsCategory[];
  categoryOrder?: NewsCategory[];
  onboarded: boolean;
};

export const INDIAN_STATES_LIST: string[] = [
  "Andhra Pradesh",
  "Arunachal Pradesh",
  "Assam",
  "Bihar",
  "Chhattisgarh",
  "Goa",
  "Gujarat",
  "Haryana",
  "Himachal Pradesh",
  "Jharkhand",
  "Karnataka",
  "Kerala",
  "Madhya Pradesh",
  "Maharashtra",
  "Manipur",
  "Meghalaya",
  "Mizoram",
  "Nagaland",
  "Odisha",
  "Punjab",
  "Rajasthan",
  "Sikkim",
  "Tamil Nadu",
  "Telangana",
  "Tripura",
  "Uttar Pradesh",
  "Uttarakhand",
  "West Bengal",
  "Delhi",
  "Jammu & Kashmir",
  "Ladakh",
];
