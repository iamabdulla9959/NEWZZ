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

  const load = useCallback(
    async (overrides?: UserPrefs, categoryFilter?: string) => {
      setLoading(true);
      setError(null);
      setCaughtUp(false);
      const p = overrides ?? currentPrefs;
      const activeCat = categoryFilter ?? selectedCategory;

      try {
        const catQuery = activeCat === "all" ? [] : [activeCat];
        const [items, seen, savedIds] = await Promise.all([
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

        // Place unseen items first, followed by seen items for an endless infinite reel
        const unseen = items.filter((c) => !seen.includes(c.id));
        const alreadySeen = items.filter((c) => seen.includes(c.id));
        const combined = unseen.length > 0 ? [...unseen, ...alreadySeen] : items;

        setCards(combined);
        setSaved(savedIds);
        setCaughtUp(combined.length === 0);
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
        <ActivityIndicator size="large" color="#7CDBD5" />
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
      />
    );
  }

  return (
    <View style={styles.container}>
      {/* Top Header with Category Selector & Actions */}
      <View style={styles.topHeader}>
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
  district: { bg: "#FF8A3D", text: "#FFFFFF", badge: "#62D394" },
  local: { bg: "#FF8A3D", text: "#FFFFFF", badge: "#62D394" },
  state: { bg: "#34C1C7", text: "#FFFFFF", badge: "#62D394" },
  national: { bg: "#4C8DFF", text: "#FFFFFF", badge: "#62D394" },
  international: { bg: "#A66BFF", text: "#FFFFFF", badge: "#62D394" },
  tech: { bg: "#34D399", text: "#0A0A0D", badge: "#62D394" },
  science: { bg: "#FF6B9D", text: "#FFFFFF", badge: "#62D394" },
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
  } else {
    const names = card.sources.map((s) => s.name);
    badgeText =
      names.length >= 2
        ? `✅ Verified by ${names[0]}, ${names[1]}`
        : names.length === 1
        ? `✅ Verified by ${names[0]}`
        : "✅ Global Verified Report";
  }

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
            colors={["rgba(10, 10, 13, 0.25)", "rgba(10, 10, 13, 0.68)", "#0A0A0D"]}
            locations={[0, 0.48, 0.92]}
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
      <View style={styles.progressBar}>
        {Array.from({ length: progressCount }, (_, index) => (
          <View
            key={index}
            style={[styles.progressSegment, index === progressIndex && styles.progressCurrent]}
          />
        ))}
      </View>
      <Text style={styles.categoryLabel}>{card.category.toUpperCase()}</Text>
      <View style={styles.caption}>
        <Text style={styles.headline} numberOfLines={3}>
          {card.headline}
        </Text>
        <Text style={styles.summary}>{card.summary}</Text>
        <Text style={styles.badge}>{badgeText}</Text>
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
      </View>
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
        <Text style={styles.swipeHint}>↺ ongoing global reels • tap 🔄 to refresh</Text>
      )}
    </SafeAreaView>
  );
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

function darkenCategory(hex: string) {
  const red = Math.round(parseInt(hex.slice(1, 3), 16) * 0.55);
  const green = Math.round(parseInt(hex.slice(3, 5), 16) * 0.55);
  const blue = Math.round(parseInt(hex.slice(5, 7), 16) * 0.55);
  return `rgb(${red}, ${green}, ${blue})`;
}

const styles = StyleSheet.create({
  pager: { flex: 1, backgroundColor: "#0A0A0D" },
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
    color: "#E0A899",
    fontSize: 13,
    textAlign: "center",
    lineHeight: 20,
    marginBottom: 20,
  },
  errorActions: { flexDirection: "row", gap: 12, flexWrap: "wrap", justifyContent: "center" },
  retry: { backgroundColor: "#7CDBD5", paddingHorizontal: 16, paddingVertical: 10, borderRadius: 10 },
  retryText: { color: "#0B0F14", fontWeight: "700", fontSize: 14 },
  resetBtn: {
    backgroundColor: "rgba(247, 37, 133, 0.15)",
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "rgba(247, 37, 133, 0.4)",
  },
  resetBtnText: { color: "#FF70A6", fontWeight: "600", fontSize: 14 },
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
  photoCredit: {
    marginTop: 8,
    alignSelf: "flex-start",
  },
  photoCreditText: {
    color: "rgba(255, 255, 255, 0.45)",
    fontSize: 10,
    fontWeight: "500",
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
    top: 10,
    left: 14,
    right: 14,
    flexDirection: "row",
    gap: 4,
    zIndex: 3,
  },
  progressSegment: { height: 3, flex: 1, backgroundColor: "rgba(255,255,255,0.28)" },
  progressCurrent: { backgroundColor: "#FFFFFF" },
  categoryLabel: {
    position: "absolute",
    top: 24,
    left: 20,
    color: "rgba(255,255,255,0.9)",
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 1,
  },
  caption: { position: "absolute", left: 20, right: 82, bottom: "11%" },
  headline: { color: "#FFFFFF", fontSize: 24, lineHeight: 29, fontWeight: "900" },
  summary: { color: "#D8DADD", fontSize: 15, lineHeight: 21, marginTop: 10 },
  badge: { color: "#62D394", fontSize: 12, fontWeight: "700", marginTop: 12 },
  actions: { position: "absolute", right: 14, bottom: "24%", alignItems: "center", gap: 16 },
  actionItem: { alignItems: "center", width: 52 },
  actionButton: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: "rgba(255,255,255,0.14)",
    alignItems: "center",
    justifyContent: "center",
  },
  actionIcon: { color: "#FFFFFF", fontSize: 21 },
  actionLabel: { color: "#D8DADD", fontSize: 10, marginTop: 4 },
  swipeHint: {
    position: "absolute",
    bottom: 26,
    alignSelf: "center",
    color: "#D8DADD",
    fontSize: 12,
  },
  container: { flex: 1, backgroundColor: "#0A0A0D" },
  topHeader: {
    position: "absolute",
    top: 46,
    left: 14,
    right: 14,
    zIndex: 10,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  categoryScrollContainer: {
    flex: 1,
    marginRight: 8,
  },
  categoryScroll: {
    flexDirection: "row",
    gap: 6,
    alignItems: "center",
  },
  categoryChip: {
    backgroundColor: "rgba(10, 10, 13, 0.72)",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.18)",
  },
  categoryChipActive: {
    backgroundColor: "#7CDBD5",
    borderColor: "#7CDBD5",
  },
  categoryChipText: {
    color: "#9AA8B8",
    fontSize: 12,
    fontWeight: "700",
  },
  categoryChipTextActive: {
    color: "#0A0A0D",
  },
  headerRightActions: {
    flexDirection: "row",
    gap: 6,
  },
  headerButton: {
    backgroundColor: "rgba(10, 10, 13, 0.72)",
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.18)",
    alignItems: "center",
    justifyContent: "center",
  },
  headerButtonText: {
    color: "#9AA8B8",
    fontSize: 12,
    fontWeight: "600",
  },
  priorityButton: {
    borderColor: "#7CDBD5",
  },
  priorityButtonText: {
    color: "#7CDBD5",
    fontSize: 12,
    fontWeight: "700",
  },
});
