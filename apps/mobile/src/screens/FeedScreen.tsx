import * as WebBrowser from "expo-web-browser";
import { LinearGradient } from "expo-linear-gradient";
import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Dimensions,
  FlatList,
  Image,
  Pressable,
  ScrollView,
  Share,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { fetchFeed, type FeedCard } from "../api";
import { loadSavedIds, loadSeenIds, markSeen, toggleSaved, clearSeenIds } from "../storage";
import type { UserPrefs } from "../types";
import { CaughtUpScreen } from "./CaughtUpScreen";
import { CategoryOrderScreen } from "./CategoryOrderScreen";
import { savePrefs } from "../storage";

const SCREEN_HEIGHT = Dimensions.get("window").height;
const PROGRESS_SEGMENT_LIMIT = 10;

const FEED_CATEGORIES = [
  { id: "all", label: "✨ For You" },
  { id: "state", label: "🗺️ State" },
  { id: "national", label: "🇮🇳 National" },
  { id: "international", label: "🌍 World" },
  { id: "politics", label: "🏛️ Politics" },
  { id: "business", label: "💼 Business" },
  { id: "health", label: "⚕️ Health" },
  { id: "sports", label: "🏅 Sports" },
  { id: "education", label: "📚 Education" },
  { id: "tech", label: "⚡ Tech" },
  { id: "science", label: "🔬 Science" },
];

type Props = {
  prefs: UserPrefs;
  onResetOnboarding?: () => void;
};

export function FeedScreen({ prefs, onResetOnboarding }: Props) {
  const [currentPrefs, setCurrentPrefs] = useState<UserPrefs>(prefs);

  useEffect(() => {
    setCurrentPrefs(prefs);
  }, [prefs]);

  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [cards, setCards] = useState<FeedCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string[]>([]);
  const [caughtUp, setCaughtUp] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [fallbackInfo, setFallbackInfo] = useState<{
    used: boolean;
    level: string | null;
    emptyReason: string | null;
  }>({ used: false, level: null, emptyReason: null });

  const load = useCallback(
    async (overrides?: UserPrefs, categoryFilter?: string) => {
      setLoading(true);
      setError(null);
      setCaughtUp(false);
      const p = overrides ?? currentPrefs;
      const activeCat = categoryFilter ?? selectedCategory;

      try {
        const catQuery = activeCat === "all" ? [] : [activeCat];
        const [feedResponse, seen, savedIds] = await Promise.all([
          fetchFeed({
            categories: catQuery,
            district: p.district,
            state: p.state,
            deviceId: p.deviceId,
            limit: 200,
          }),
          loadSeenIds(),
          loadSavedIds(),
        ]);

        const items = feedResponse.items;
        setFallbackInfo({
          used: feedResponse.fallbackUsed,
          level: feedResponse.fallbackLevel,
          emptyReason: feedResponse.emptyReason,
        });

        // Maintain strict importance/priority ranking from the API
        setCards(items);
        setSaved(savedIds);
        setCaughtUp(items.length === 0);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not load feed");
      } finally {
        setLoading(false);
      }
    },
    [currentPrefs, selectedCategory]
  );

  const handleCategorySelect = (catId: string) => {
    setSelectedCategory(catId);
    void load(currentPrefs, catId);
  };

  const handleClearSeen = async () => {
    await clearSeenIds();
    void load(currentPrefs, selectedCategory);
  };

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#EB7D00" />
        <Text style={styles.loadingText}>Fetching ongoing global reels...</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.center}>
        <View style={styles.errorBox}>
          <Text style={styles.errorIcon}>⚠️</Text>
          <Text style={styles.errorTitle}>Could Not Load Feed</Text>
          <Text style={styles.errorDesc}>{error}</Text>
          <View style={styles.errorActions}>
            <Pressable onPress={() => void load()} style={styles.retry}>
              <Text style={styles.retryText}>🔄 Try Again</Text>
            </Pressable>
            {onResetOnboarding && (
              <Pressable onPress={onResetOnboarding} style={styles.resetBtn}>
                <Text style={styles.resetBtnText}>⚙️ Reset Onboarding</Text>
              </Pressable>
            )}
          </View>
        </View>
      </View>
    );
  }

  if (showSettings) {
    return (
      <CategoryOrderScreen
        prefs={currentPrefs}
        isSettings={true}
        onDone={async (next) => {
          await savePrefs(next);
          setCurrentPrefs(next);
          setShowSettings(false);
          void load(next, selectedCategory);
        }}
      />
    );
  }

  if (caughtUp && cards.length === 0) {
    return (
      <CaughtUpScreen
        onRefresh={() => void load()}
        onResetOnboarding={onResetOnboarding}
        onClearSeen={handleClearSeen}
        prefs={currentPrefs}
        fallbackLevel={fallbackInfo.level}
        emptyReason={fallbackInfo.emptyReason}
      />
    );
  }

  return (
    <View style={styles.container}>
      {/* Unified Top Navigation Header */}
      <View style={styles.topBarContainer}>
        <View style={styles.topBarHeaderRow}>
          <View style={styles.locationBadgeContainer}>
            <Text style={styles.locationText}>
              📍 {currentPrefs.state || "All India"}
            </Text>
            {fallbackInfo.used && (
              <Text style={styles.fallbackWarning}>
                ⚠️ Showing {fallbackInfo.level}
              </Text>
            )}
          </View>

          <View style={styles.headerRightActions}>
            <Pressable
              style={styles.headerButton}
              onPress={() => void load(currentPrefs, selectedCategory)}
              accessibilityLabel="Refresh news"
            >
              <Text style={styles.headerButtonText}>🔄</Text>
            </Pressable>
            {onResetOnboarding && (
              <Pressable
                style={styles.headerButton}
                onPress={onResetOnboarding}
                accessibilityLabel="Reset onboarding preferences"
              >
                <Text style={styles.headerButtonText}>⚙️</Text>
              </Pressable>
            )}
            <Pressable
              style={[styles.headerButton, styles.priorityButton]}
              onPress={() => setShowSettings(true)}
              accessibilityLabel="Edit category priority ranking"
            >
              <Text style={styles.priorityButtonText}>⚡</Text>
            </Pressable>
          </View>
        </View>

        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.categoryScroll}
          style={styles.categoryScrollContainer}
        >
          {FEED_CATEGORIES.map((cat) => (
            <Pressable
              key={cat.id}
              style={[
                styles.categoryChip,
                selectedCategory === cat.id && styles.categoryChipActive,
              ]}
              onPress={() => handleCategorySelect(cat.id)}
            >
              <Text
                style={[
                  styles.categoryChipText,
                  selectedCategory === cat.id && styles.categoryChipTextActive,
                ]}
              >
                {cat.label}
              </Text>
            </Pressable>
          ))}
        </ScrollView>
      </View>

      {/* Infinite Stories Carousel */}
      <FlatList
        style={styles.pager}
        data={cards}
        keyExtractor={(item, index) => `${item.id}-${index}`}
        pagingEnabled={true}
        snapToInterval={SCREEN_HEIGHT}
        decelerationRate="fast"
        showsVerticalScrollIndicator={false}
        getItemLayout={(_, index) => ({
          length: SCREEN_HEIGHT,
          offset: SCREEN_HEIGHT * index,
          index,
        })}
        renderItem={({ item, index }) => (
          <View style={styles.page}>
            <StoryCard
              card={item}
              saved={saved.includes(item.id)}
              isFirst={index === 0}
              isLast={index === cards.length - 1}
              progressCount={Math.min(cards.length, PROGRESS_SEGMENT_LIMIT)}
              progressIndex={Math.min(index, PROGRESS_SEGMENT_LIMIT - 1)}
              onSave={async () => setSaved(await toggleSaved(item.id))}
            />
          </View>
        )}
        onMomentumScrollEnd={(event) => {
          const index = Math.round(event.nativeEvent.contentOffset.y / SCREEN_HEIGHT);
          if (index >= 0 && index < cards.length) {
            void markSeen([cards[index].id]);
          }
        }}
      />
    </View>
  );
}

const CATEGORY_COLORS: Record<string, { bg: string; text: string; badge: string }> = {
  district: { bg: "#EB7D00", text: "#0A0A0D", badge: "#2C5745" },
  local: { bg: "#EB7D00", text: "#0A0A0D", badge: "#2C5745" },
  state: { bg: "#EB7D00", text: "#0A0A0D", badge: "#2C5745" },
  national: { bg: "#EB7D00", text: "#0A0A0D", badge: "#2C5745" },
  international: { bg: "#EB7D00", text: "#0A0A0D", badge: "#2C5745" },
  tech: { bg: "#EB7D00", text: "#0A0A0D", badge: "#2C5745" },
  science: { bg: "#EB7D00", text: "#0A0A0D", badge: "#2C5745" },
};

function StoryCard({
  card,
  saved,
  isFirst,
  isLast,
  progressCount,
  progressIndex,
  onSave,
}: {
  card: FeedCard;
  saved: boolean;
  isFirst: boolean;
  isLast: boolean;
  progressCount: number;
  progressIndex: number;
  onSave: () => void;
}) {
  const catTheme = CATEGORY_COLORS[card.category.toLowerCase()] ?? CATEGORY_COLORS.international;

  let badgeText = "Verification pending";
  if (card.verification_type === "official_source") {
    badgeText = "🏛️ Official Source";
  } else if (card.verification_type === "flagged_conflict") {
    badgeText = "⚠️ Conflicting Reports";
  } else if (card.sources.length === 1) {
    const name = card.sources[0]?.name;
    badgeText = name ? `📰 Sourced from ${name}` : "📰 Single Source";
  } else {
    const names = card.sources.map((s) => s.name);
    badgeText =
      names.length >= 2
        ? `📰 Multi-Source (${names.length} verified)`
        : names.length === 1
        ? `📰 Sourced from ${names[0]}`
        : "📰 Sourced Report";
  }

  // Deduplicate sources by publisher name
  const uniqueSources = Array.from(
    new Map(card.sources.map((s) => [s.name, s])).values()
  );

  return (
    <SafeAreaView style={styles.story} edges={["top", "bottom"]}>
      {card.image_url ? (
        <>
          <Image
            source={{ uri: card.image_url }}
            style={styles.backgroundImage}
            resizeMode="cover"
          />
          <LinearGradient
            colors={["rgba(10, 10, 13, 0.40)", "rgba(10, 10, 13, 0.75)", "#0A0A0D"]}
            locations={[0, 0.45, 0.95]}
            style={styles.gradient}
          />
        </>
      ) : (
        <>
          <LinearGradient
            colors={["#EB7D00", "#EBE3A7", "#2C5745", "#2E2910", "#0A0A0D"]}
            locations={[0, 0.25, 0.5, 0.75, 1]}
            style={styles.gradient}
          />
          <Text style={styles.categoryTexture}>{categoryIcon(card.category)}</Text>
        </>
      )}

      {/* Segmented Progress Bar */}
      <View style={styles.progressBar}>
        {Array.from({ length: progressCount }, (_, index) => (
          <View
            key={index}
            style={[styles.progressSegment, index === progressIndex && styles.progressCurrent]}
          />
        ))}
      </View>

      {/* Main Content Area - Scrollable to ensure no text is ever clipped */}
      <ScrollView
        style={styles.storyContentScroll}
        contentContainerStyle={styles.storyContentContainer}
        showsVerticalScrollIndicator={false}
      >
        {/* Category & Time Badge Row */}
        <View style={styles.metaBadgeRow}>
          <View style={[styles.categoryBadge, { backgroundColor: catTheme.bg }]}>
            <Text style={[styles.categoryBadgeText, { color: catTheme.text }]}>
              {categoryIcon(card.category)} {card.category.toUpperCase()}
            </Text>
          </View>
          <Text style={styles.whenText}>
            • {formatStoryTime(card.published_at ?? card.created_at)}
          </Text>
          {card.priority_score >= 8 && (
            <View style={styles.breakingBadge}>
              <Text style={styles.breakingBadgeText}>🔥 Top Story</Text>
            </View>
          )}
        </View>

        {/* Headline */}
        <Text style={styles.headline}>
          {card.headline}
        </Text>

        {/* Summary with paragraphs */}
        <View style={styles.summaryContainer}>
          {formatCardSummary(card.summary).map((para, pIdx) => (
            <Text key={pIdx} style={styles.summaryParagraph}>
              {para}
            </Text>
          ))}
        </View>

        {/* Trust & Corroboration Badge */}
        <View style={styles.trustBadgeContainer}>
          <Text style={styles.badge}>{badgeText}</Text>
          <Text style={styles.whyShown}>
            {card.priority_score >= 8 ? "Why shown: High-impact breaking news" : "Why shown: Matches your interests"}
            {card.district ? ` • Local to ${card.district}` : ""}
            {card.state ? ` • ${card.state}` : ""}
          </Text>
        </View>

        {/* Deduplicated Source Chips */}
        <View style={styles.sourceChipRow}>
          {uniqueSources.map((source) => (
            <Pressable
              key={`${source.source_id}-${source.url}`}
              style={styles.sourceChip}
              onPress={() => void WebBrowser.openBrowserAsync(source.url)}
              accessibilityLabel={`Open source: ${source.name}`}
            >
              <Text style={styles.sourceChipText}>📰 {source.name} ↗</Text>
            </Pressable>
          ))}
        </View>

        {card.image_author && (
          <Pressable
            style={styles.photoCredit}
            onPress={() => {
              if (card.image_author_url) {
                void WebBrowser.openBrowserAsync(card.image_author_url);
              }
            }}
          >
            <Text style={styles.photoCreditText}>
              📷 Photo by {card.image_author} on Unsplash
            </Text>
          </Pressable>
        )}
      </ScrollView>

      {/* Floating Action Buttons */}
      <View style={styles.actions}>
        <ActionButton label={saved ? "Saved" : "Save"} icon="🔖" onPress={onSave} />
        <ActionButton
          label="Share"
          icon="🔗"
          onPress={() => void Share.share({ message: `${card.headline}\n\n${card.summary}` })}
        />
        <ActionButton
          label="Story"
          icon="↗"
          onPress={() => {
            const url = card.sources[0]?.url;
            if (url) void WebBrowser.openBrowserAsync(url);
          }}
        />
      </View>

      {isFirst && <Text style={styles.swipeHint}>︿ swipe up for next story</Text>}
      {isLast && !isFirst && (
        <Text style={styles.swipeHint}>↺ ongoing reels • tap 🔄 to refresh</Text>
      )}
    </SafeAreaView>
  );
}

function formatCardSummary(summary: string): string[] {
  if (!summary) return [];
  if (summary.includes("\n\n")) {
    return summary.split("\n\n").map((p) => p.trim()).filter(Boolean);
  }
  const sentences = summary.match(/[^.!?]+[.!?]+(\s|$)/g) || [summary];
  if (sentences.length <= 2) {
    return [summary];
  } else if (sentences.length === 3 || sentences.length === 4) {
    const mid = Math.ceil(sentences.length / 2);
    return [sentences.slice(0, mid).join("").trim(), sentences.slice(mid).join("").trim()];
  } else {
    const p1 = sentences.slice(0, 2).join("").trim();
    const p2 = sentences.slice(2, 4).join("").trim();
    const p3 = sentences.slice(4).join("").trim();
    return [p1, p2, p3].filter(Boolean);
  }
}

function formatStoryTime(value: string | null): string {
  if (!value) return "Published time unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Published time unavailable";
  return `Published ${date.toLocaleDateString(undefined, { month: "short", day: "numeric" })}`;
}

function ActionButton({
  label,
  icon,
  onPress,
}: {
  label: string;
  icon: string;
  onPress: () => void;
}) {
  return (
    <View style={styles.actionItem}>
      <Pressable onPress={onPress} style={styles.actionButton} accessibilityLabel={label}>
        <Text style={styles.actionIcon}>{icon}</Text>
      </Pressable>
      <Text style={styles.actionLabel}>{label}</Text>
    </View>
  );
}

function categoryIcon(category: string) {
  const icons: Record<string, string> = {
    district: "⌂",
    local: "⌂",
    state: "⌖",
    national: "✦",
    international: "◎",
    tech: "⌘",
    science: "⚗",
  };
  return icons[category.toLowerCase()] ?? "✦";
}


const styles = StyleSheet.create({
  pager: { flex: 1, width: "100%", maxWidth: 540, backgroundColor: "#0A0A0D" },
  page: { width: "100%", height: SCREEN_HEIGHT },
  center: {
    flex: 1,
    backgroundColor: "#0B0F14",
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
  },
  loadingText: { color: "#9AA8B8", fontSize: 14, marginTop: 12 },
  errorBox: {
    backgroundColor: "#16222F",
    borderRadius: 16,
    padding: 24,
    borderWidth: 1,
    borderColor: "#E63946",
    alignItems: "center",
    maxWidth: 380,
    width: "100%",
  },
  errorIcon: { fontSize: 32, marginBottom: 8 },
  errorTitle: { color: "#F4F7FB", fontSize: 20, fontWeight: "700", marginBottom: 8 },
  errorDesc: {
    color: "#EBE3A7",
    fontSize: 13,
    textAlign: "center",
    lineHeight: 20,
    marginBottom: 20,
  },
  errorActions: { flexDirection: "row", gap: 12, flexWrap: "wrap", justifyContent: "center" },
  retry: { backgroundColor: "#EB7D00", paddingHorizontal: 16, paddingVertical: 10, borderRadius: 10 },
  retryText: { color: "#0B0F14", fontWeight: "700", fontSize: 14 },
  resetBtn: {
    backgroundColor: "rgba(235,125,0,0.15)",
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "rgba(235,125,0,0.4)",
  },
  resetBtnText: { color: "#EBE3A7", fontWeight: "600", fontSize: 14 },
  story: {
    flex: 1,
    width: "100%",
    height: SCREEN_HEIGHT,
    backgroundColor: "#0A0A0D",
    overflow: "hidden",
  },
  backgroundImage: {
    ...StyleSheet.absoluteFillObject,
    width: "100%",
    height: SCREEN_HEIGHT,
  },
  gradient: { ...StyleSheet.absoluteFillObject },
  categoryTexture: {
    position: "absolute",
    top: "23%",
    alignSelf: "center",
    color: "rgba(255,255,255,0.08)",
    fontSize: 170,
  },
  progressBar: {
    position: "absolute",
    top: 6,
    left: 14,
    right: 14,
    flexDirection: "row",
    gap: 4,
    zIndex: 25,
  },
  progressSegment: { height: 3, flex: 1, backgroundColor: "rgba(255,255,255,0.28)", borderRadius: 2 },
  progressCurrent: { backgroundColor: "#FFFFFF" },

  storyContentScroll: {
    flex: 1,
    width: "100%",
    marginTop: 88,
    marginBottom: 36,
  },
  storyContentContainer: {
    paddingHorizontal: 18,
    paddingRight: 72,
    paddingBottom: 50,
  },

  metaBadgeRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: 10,
    flexWrap: "wrap",
  },
  categoryBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  categoryBadgeText: {
    fontSize: 11,
    fontWeight: "900",
    letterSpacing: 0.8,
  },
  whenText: { color: "#9AA8B8", fontSize: 11, fontWeight: "500" },
  breakingBadge: {
    backgroundColor: "rgba(235, 60, 60, 0.25)",
    borderColor: "#FF4D4D",
    borderWidth: 1,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  breakingBadgeText: {
    color: "#FF6B6B",
    fontSize: 10,
    fontWeight: "800",
    letterSpacing: 0.5,
  },

  headline: {
    color: "#FFFFFF",
    fontSize: 21,
    lineHeight: 27,
    fontWeight: "900",
    letterSpacing: -0.3,
    marginBottom: 12,
  },

  summaryContainer: {
    marginBottom: 14,
    gap: 10,
  },
  summaryParagraph: {
    color: "#E2E4E8",
    fontSize: 14,
    lineHeight: 21,
    letterSpacing: 0.1,
  },

  trustBadgeContainer: {
    backgroundColor: "rgba(255, 255, 255, 0.05)",
    borderColor: "rgba(255, 255, 255, 0.1)",
    borderWidth: 1,
    borderRadius: 8,
    padding: 10,
    marginBottom: 12,
  },
  badge: { color: "#EBE3A7", fontSize: 12, fontWeight: "700" },
  whyShown: { color: "#9AA8B8", fontSize: 11, lineHeight: 15, marginTop: 4 },

  sourceChipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    marginBottom: 8,
  },
  sourceChip: {
    backgroundColor: "rgba(235, 125, 0, 0.15)",
    borderColor: "rgba(235, 125, 0, 0.35)",
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  sourceChipText: {
    color: "#EBE3A7",
    fontSize: 11,
    fontWeight: "600",
  },

  photoCredit: {
    marginTop: 8,
    alignSelf: "flex-start",
  },
  photoCreditText: {
    color: "rgba(255, 255, 255, 0.45)",
    fontSize: 10,
    fontWeight: "500",
  },

  actions: {
    position: "absolute",
    right: 12,
    bottom: "20%",
    alignItems: "center",
    gap: 14,
    zIndex: 15,
  },
  actionItem: { alignItems: "center", width: 52 },
  actionButton: {
    width: 46,
    height: 46,
    borderRadius: 23,
    backgroundColor: "rgba(255,255,255,0.16)",
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.12)",
  },
  actionIcon: { color: "#FFFFFF", fontSize: 20 },
  actionLabel: { color: "#D8DADD", fontSize: 10, marginTop: 4, fontWeight: "600" },

  swipeHint: {
    position: "absolute",
    bottom: 14,
    alignSelf: "center",
    color: "rgba(216, 218, 221, 0.7)",
    fontSize: 11,
    letterSpacing: 0.5,
  },

  container: { flex: 1, backgroundColor: "#0A0A0D", alignItems: "center" },

  topBarContainer: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    zIndex: 20,
    paddingTop: 12,
    paddingBottom: 8,
    paddingHorizontal: 14,
    backgroundColor: "rgba(10, 10, 13, 0.92)",
    borderBottomWidth: 1,
    borderBottomColor: "rgba(255, 255, 255, 0.08)",
  },
  topBarHeaderRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 8,
  },
  locationBadgeContainer: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  locationText: {
    color: "#EBE3A7",
    fontSize: 12,
    fontWeight: "700",
    backgroundColor: "rgba(235, 125, 0, 0.18)",
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "rgba(235, 125, 0, 0.3)",
  },
  fallbackWarning: {
    color: "#0A0A0D",
    backgroundColor: "#EB7D00",
    fontSize: 11,
    fontWeight: "700",
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
  },
  headerRightActions: {
    flexDirection: "row",
    gap: 6,
  },
  headerButton: {
    backgroundColor: "rgba(255, 255, 255, 0.08)",
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.14)",
    alignItems: "center",
    justifyContent: "center",
  },
  headerButtonText: {
    color: "#9AA8B8",
    fontSize: 12,
    fontWeight: "600",
  },
  priorityButton: {
    borderColor: "#EB7D00",
    backgroundColor: "rgba(235, 125, 0, 0.12)",
  },
  priorityButtonText: {
    color: "#EB7D00",
    fontSize: 12,
    fontWeight: "700",
  },
  categoryScrollContainer: {
    width: "100%",
  },
  categoryScroll: {
    flexDirection: "row",
    gap: 6,
    alignItems: "center",
  },
  categoryChip: {
    backgroundColor: "rgba(255, 255, 255, 0.08)",
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.12)",
  },
  categoryChipActive: {
    backgroundColor: "#EB7D00",
    borderColor: "#EB7D00",
  },
  categoryChipText: {
    color: "#9AA8B8",
    fontSize: 12,
    fontWeight: "700",
  },
  categoryChipTextActive: {
    color: "#0A0A0D",
  },
});
