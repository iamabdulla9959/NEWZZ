export type NewsCategory =
  | "district"
  | "state"
  | "national"
  | "international"
  | "tech"
  | "science";

export type TrustTier = 1 | 2 | 3 | "1" | "2" | "3" | "official_local";

export type VerificationType =
  | "cross_verified"
  | "official_source"
  | "flagged_conflict";

export type VerifiedStatus =
  | "draft"
  | "pending_review"
  | "published"
  | "rejected"
  | "flagged_conflict";

export interface SourceSchema {
  id: string;
  name: string;
  category: NewsCategory;
  region: string | null;
  rssUrl: string | null;
  trustTier: TrustTier;
  isActive: boolean;
}

export interface CardSourceRef {
  sourceId: string;
  name: string;
  url: string;
  trustTier: TrustTier;
}

export interface CardSchema {
  id: string;
  headline: string;
  summary: string;
  category: NewsCategory;
  sources: CardSourceRef[];
  verifiedStatus: VerifiedStatus;
  verificationType?: VerificationType | null;
  createdAt: string;
}

export const DEFAULT_ONBOARDING_CATEGORIES: NewsCategory[] = [
  "district",
  "state",
  "national",
  "international",
  "tech",
];
