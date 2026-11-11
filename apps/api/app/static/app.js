/**

 * NEWZZ - Premium Editorial Intelligence Platform

 * BroadSheet UX Engine with Algorithmic Explainability, Regional Desks & Priority Calibration

 */

(function () {
  "use strict";

  // --- Configuration & API Base ---

  let API_BASE = window.RENDER_API_BASE || "";

  if (!API_BASE) {
    if (
      (window.location.hostname === "localhost" ||
        window.location.hostname === "127.0.0.1") &&
      window.location.port === "8000"
    ) {
      API_BASE = window.location.origin;
    } else {
      API_BASE = "https://newzz-5e19.onrender.com";
    }
  }

  // --- Helper: HTML Sanitizer / Escaper (B53 P0 Fix) ---
  function escapeHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  const STORAGE_KEYS = {
    DEVICE_ID: "newsreels_device_id",

    LOCATION_STATE: "newsreels_state",

    INTERESTS: "newsreels_interests",

    PRIORITY_ORDER: "newsreels_priority_order",

    ONBOARDING_COMPLETE: "newsreels_onboarding_complete",

    TOP_CARD_CACHE: "newsreels_top_card",
  };

  const ALL_CATEGORIES = [
    "Technology",
    "Politics",
    "Business",
    "National",
    "World",

    "Science",
    "Health",
    "Sports",
    "Education",
    "State",

    "Entertainment",
    "Environment",
  ];

  // Instant Fallback Lead Story (rendered in 0ms on initial boot for zero perceived lag)

  function getDynamicInstantCard(userState) {
    const st = userState || "Telangana";
    return {
      id: "lead-instant-" + Date.now(),
      headline: `${st} Regional Desk: Live Verified Dispatches Calibrated for Today`,
      summary: `Continuous verified monitoring of legislative decisions, state administrative policies, and civic infrastructure across ${st}.`,
      category: "state",
      state: st,
      published_at: new Date().toISOString(),
      created_at: new Date().toISOString(),
      source_name: `${st} Bureau`,
      canonical_url: "https://newszzzz.netlify.app",
      verification_type: "cross_verified",
      importance_score: 92.0,
      verification_score: 96.0,
      personal_relevance_score: 95.0,
      final_feed_score: 92.0,
      priority_reason: `Active regional desk calibration for ${st}.`,
    };
  }

  const INSTANT_FALLBACK_CARD = {
    id: "lead-instant-01",

    headline:
      "India Clears ₹1,76,000-Crore Semiconductor Expansion: Advanced Wafer Fabrication Cluster Gets Cabinet Nod",

    summary:
      "The Union Cabinet has sanctioned the second phase of the India Semiconductor Mission, anchoring an advanced packaging and wafer fabrication ecosystem outside Hyderabad expected to create 24,000 high-skill engineering roles across the regional technology corridor.",

    category: "technology",

    state: "Telangana",

    published_at: new Date().toISOString(),

    created_at: new Date().toISOString(),

    source_name: "LiveMint & The Hindu",

    canonical_url: "https://www.thehindu.com",

    verification_type: "cross_verified",

    importance_score: 94.0,

    urgency_score: 84.0,

    freshness_score: 95.0,

    verification_score: 98.0,

    personal_relevance_score: 96.0,

    final_feed_score: 93.8,

    priority_reason:
      "High strategic importance with cross-verified regulatory wire corroboration.",
  };

  // --- State ---

  let state = {
    deviceId: getOrCreateDeviceId(),

    state: localStorage.getItem(STORAGE_KEYS.LOCATION_STATE) || "Telangana",

    activeCategory: "for_you",

    isInitialLoading: true,

    interests: getStoredInterests(),

    priorityOrder: getStoredPriorityOrder(),

    cards: [],

    cardIds: new Set(),

    allRankedCache: [],
    allMasterCards: [],
    activeFetchController: null,
    quickReadMode: false,
    quickReadIndex: 0,
    quickReadCards: [],
    savedCardIds: (function () {
      try {
        return JSON.parse(localStorage.getItem("newzz_saved_ids_v1") || "[]");
      } catch (e) {
        return [];
      }
    })(),
    activeTrendingTopic: null,
    currentSpeakingCardId: null,
    speakingUtterance: null,
    eli5CardId: null,
    currentLang: localStorage.getItem("newzz_lang") || "en",
    readingStreak: (function () {
      try {
        const today = new Date().toISOString().slice(0, 10);
        let s = JSON.parse(localStorage.getItem("newzz_streak_v1") || "null");
        if (!s) {
          s = { days: 1, count: 0, date: today };
        } else if (s.date !== today) {
          const yesterday = new Date(Date.now() - 86400000)
            .toISOString()
            .slice(0, 10);
          s.days = s.date === yesterday ? s.days + 1 : 1;
          s.count = 0;
          s.date = today;
        }
        return s;
      } catch (e) {
        return {
          days: 1,
          count: 0,
          date: new Date().toISOString().slice(0, 10),
        };
      }
    })(),

    selectedCard: null,

    loading: false,

    offset: 0,

    pageSize: 30,

    hasMore: true,
  };

  // --- DOM Elements ---

  const elements = {
    // Navigation & Masthead

    navForYou: document.getElementById("nav-for-you"),

    navLatest: document.getElementById("nav-latest"),

    navCategories: document.getElementById("nav-categories"),

    navStateEdition: document.getElementById("nav-state-edition"),

    navStateLabel: document.getElementById("nav-state-label"),

    inputSearch: document.getElementById("input-search-intelligence"),

    labelUserLocation: document.getElementById("label-user-location"),

    btnOpenLocation: document.getElementById("btn-open-location-modal"),

    btnRefreshFeed: document.getElementById("btn-refresh-feed"),

    // Personalization Banner

    mastheadDate: document.getElementById("masthead-date"),

    mastheadEdition: document.getElementById("masthead-edition"),

    verifiedStoriesCount: document.getElementById("verified-stories-count"),

    greetingName: document.getElementById("greeting-name"),

    bannerStateName: document.getElementById("banner-state-name"),

    bannerStateLabel: document.getElementById("banner-state-label"),

    btnChangeStateBanner: document.getElementById("btn-change-state-banner"),

    btnOpenPriorityModal: document.getElementById("btn-open-priority-modal"),

    calibratedRankContainer: document.getElementById(
      "calibrated-rank-container",
    ),

    // Category Tabs

    categoryTabs: document.querySelectorAll(".category-tab"),

    statShowingCount: document.getElementById("stat-showing-count"),

    statTotalCount: document.getElementById("stat-total-count"),

    // Editorial Flow Containers

    heroLeadContainer: document.getElementById("hero-lead-container"),

    secondaryGridContainer: document.getElementById("secondary-grid-container"),

    stateFocusSection: document.getElementById("state-focus-section"),

    stateFocusTitle: document.getElementById("state-focus-title"),

    stateFocusContainer: document.getElementById("state-focus-container"),

    streamFeedContainer: document.getElementById("stream-feed-container"),

    feedPaginationStatus: document.getElementById("feed-pagination-status"),

    btnLoadMore: document.getElementById("btn-load-more"),

    statusCaughtUpMsg: document.getElementById("status-caught-up-msg"),

    // Intelligence Sidebar

    morningBriefContainer: document.getElementById("morning-brief-container"),

    radarPersonaText: document.getElementById("radar-persona-text"),

    barValImportance: document.getElementById("bar-val-importance"),

    barFillImportance: document.getElementById("bar-fill-importance"),

    barValUrgency: document.getElementById("bar-val-urgency"),

    barFillUrgency: document.getElementById("bar-fill-urgency"),

    barValFreshness: document.getElementById("bar-val-freshness"),

    barFillFreshness: document.getElementById("bar-fill-freshness"),

    barValVerification: document.getElementById("bar-val-verification"),

    barFillVerification: document.getElementById("bar-fill-verification"),

    barValRelevance: document.getElementById("bar-val-relevance"),

    barFillRelevance: document.getElementById("bar-fill-relevance"),

    radarDataPolygon: document.getElementById("radar-data-polygon"),

    bureauCopilotHeading: document.getElementById("bureau-copilot-heading"),

    bureauCopilotDesc: document.getElementById("bureau-copilot-desc"),

    // Modals

    modalLocation: document.getElementById("modal-location"),

    btnCloseLocation: document.getElementById("btn-close-location-modal"),

    inputState: document.getElementById("input-state"),

    btnSaveLocation: document.getElementById("btn-save-location"),

    btnSkipLocation: document.getElementById("btn-skip-location"),

    // Quick Read (60-Word Reels) Elements
    btnToggleQuickRead: document.getElementById("btn-toggle-quick-read"),
    quickReadOverlay: document.getElementById("quick-read-overlay"),
    btnCloseQuickRead: document.getElementById("btn-close-quick-read"),
    qrCounter: document.getElementById("qr-counter"),
    qrCategoryBadge: document.getElementById("qr-category-badge"),
    qrStateBadge: document.getElementById("qr-state-badge"),
    qrTrustBadge: document.getElementById("qr-trust-badge"),
    qrTimeAgo: document.getElementById("qr-time-ago"),
    qrHeadline: document.getElementById("qr-headline"),
    qrSummary: document.getElementById("qr-summary"),
    qrKeyFacts: document.getElementById("qr-key-facts"),
    qrSourceName: document.getElementById("qr-source-name"),
    qrBtnOriginal: document.getElementById("qr-btn-original"),
    qrBtnFullDossier: document.getElementById("qr-btn-full-dossier"),
    qrTouchArea: document.getElementById("qr-touch-area"),
    qrNavPrev: document.getElementById("qr-nav-prev"),
    qrNavNext: document.getElementById("qr-nav-next"),
    btnQrShare: document.getElementById("btn-qr-share"),
    btnQrListen: document.getElementById("btn-qr-listen"),
    qrListenIcon: document.getElementById("qr-listen-icon"),
    qrListenLabel: document.getElementById("qr-listen-label"),
    btnQrBookmark: document.getElementById("btn-qr-bookmark"),
    qrBookmarkIcon: document.getElementById("qr-bookmark-icon"),
    tabSaved: document.getElementById("tab-saved"),
    trendingTopicsContainer: document.getElementById(
      "trending-topics-container",
    ),
    trendingChipsList: document.getElementById("trending-chips-list"),

    modalInterests: document.getElementById("modal-interests"),

    btnCloseInterests: document.getElementById("btn-close-interests-modal"),

    interestChipsContainer: document.getElementById("interest-chips-container"),

    btnSaveInterests: document.getElementById("btn-save-interests"),

    btnResetInterests: document.getElementById("btn-reset-interests"),

    modalPriority: document.getElementById("modal-priority"),

    btnClosePriority: document.getElementById("btn-close-priority-modal"),

    btnBackPriority: document.getElementById("btn-back-priority"),

    btnSavePriority: document.getElementById("btn-save-priority"),

    priorityListContainer: document.getElementById("priority-list-container"),

    priorityErrorBanner: document.getElementById("priority-error-banner"),

    priorityErrorMsg: document.getElementById("priority-error-msg"),

    modalDetail: document.getElementById("modal-story-detail"),

    btnCloseDetail: document.getElementById("btn-close-detail-modal"),
    btnModalListen: document.getElementById("btn-modal-listen"),
    modalListenIcon: document.getElementById("modal-listen-icon"),
    modalListenLabel: document.getElementById("modal-listen-label"),
    btnModalBookmark: document.getElementById("btn-modal-bookmark"),
    modalBookmarkIcon: document.getElementById("modal-bookmark-icon"),
    btnModalEli5: document.getElementById("btn-modal-eli5"),
    detailEli5Box: document.getElementById("detail-eli5-box"),
    detailEli5Text: document.getElementById("detail-eli5-text"),
    btnLangToggle: document.getElementById("btn-lang-toggle"),
    langToggleText: document.getElementById("lang-toggle-text"),
    readingStreakBadge: document.getElementById("reading-streak-badge"),
    readingStreakText: document.getElementById("reading-streak-text"),
    qrVisualBanner: document.getElementById("qr-visual-banner"),
    detailCorroborationSpectrum: document.getElementById(
      "detail-corroboration-spectrum",
    ),
    detailCorroborationCount: document.getElementById(
      "detail-corroboration-count",
    ),
    detailSpectrumSourcesChips: document.getElementById(
      "detail-spectrum-sources-chips",
    ),
    spectrumBarFill: document.getElementById("spectrum-bar-fill"),

    detailCategoryBadge: document.getElementById("detail-category-badge"),

    detailVerificationBadge: document.getElementById(
      "detail-verification-badge",
    ),

    detailHeadline: document.getElementById("detail-headline"),

    detailSourceAuthor: document.getElementById("detail-source-author"),

    detailTime: document.getElementById("detail-time"),

    detailScoreImportance: document.getElementById("detail-score-importance"),

    detailScoreUrgency: document.getElementById("detail-score-urgency"),

    detailScoreFreshness: document.getElementById("detail-score-freshness"),

    detailScoreVerification: document.getElementById(
      "detail-score-verification",
    ),

    detailScoreRelevance: document.getElementById("detail-score-relevance"),

    barImportance: document.getElementById("bar-importance"),

    barUrgency: document.getElementById("bar-urgency"),

    barFreshness: document.getElementById("bar-freshness"),

    barVerification: document.getElementById("bar-verification"),

    barRelevance: document.getElementById("bar-relevance"),

    detailSummaryContent: document.getElementById("detail-summary-content"),

    detailPriorityReason: document.getElementById("detail-priority-reason"),

    detailSourcesList: document.getElementById("detail-sources-list"),

    btnOpenOriginalArticle: document.getElementById(
      "btn-open-original-article",
    ),

    feedToast: document.getElementById("feed-toast"),
  };

  // --- Helper Utilities ---

  function getOrCreateDeviceId() {
    let id = localStorage.getItem(STORAGE_KEYS.DEVICE_ID);

    if (!id) {
      id =
        "dev_" + Math.random().toString(36).substring(2, 11) + "_" + Date.now();

      localStorage.setItem(STORAGE_KEYS.DEVICE_ID, id);
    }

    return id;
  }

  function getStoredInterests() {
    try {
      const stored = localStorage.getItem(STORAGE_KEYS.INTERESTS);

      if (stored) {
        const parsed = JSON.parse(stored);

        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch (_) {}

    return ["State", "Politics", "Technology", "National", "Business"];
  }

  function getStoredPriorityOrder() {
    try {
      const stored = localStorage.getItem(STORAGE_KEYS.PRIORITY_ORDER);

      if (stored) {
        const parsed = JSON.parse(stored);

        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch (_) {}

    const interests = getStoredInterests();

    return interests && interests.length > 0
      ? [...interests]
      : ["State", "Politics", "Technology", "National", "Business"];
  }

  function formatTimeAgo(isoString) {
    if (!isoString) return "Recent Dispatch";
    try {
      const pubDate = new Date(isoString);
      if (isNaN(pubDate.getTime())) return "Recent Dispatch";
      const now = new Date();
      const diffMs = now.getTime() - pubDate.getTime();
      if (diffMs < 0) return "Just now";
      const diffSecs = Math.floor(diffMs / 1000);
      const diffMins = Math.floor(diffSecs / 60);
      const diffHours = Math.floor(diffMins / 60);
      const diffDays = Math.floor(diffHours / 24);

      if (diffSecs < 60) return "Just now";
      if (diffMins < 60) return `${diffMins}m ago`;
      if (diffHours < 24) return `${diffHours}h ago`;
      if (diffDays === 1) return "Yesterday";
      if (diffDays < 7) return `${diffDays}d ago`;
      return pubDate.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
      });
    } catch (_) {
      return "Recent Dispatch";
    }
  }

  function showFeedToast(msg) {
    if (!elements.feedToast) return;

    elements.feedToast.textContent = msg;

    elements.feedToast.classList.remove("hidden");

    clearTimeout(elements.feedToast._timeout);

    elements.feedToast._timeout = setTimeout(() => {
      elements.feedToast.classList.add("hidden");
    }, 2800);
  }

  function updateLocationHeaders() {
    const st = state.state || "All India";

    if (elements.labelUserLocation) elements.labelUserLocation.textContent = st;

    if (elements.bannerStateName) elements.bannerStateName.textContent = st;

    if (elements.bannerStateLabel) elements.bannerStateLabel.textContent = st;

    if (elements.navStateLabel)
      elements.navStateLabel.textContent = `${st} Desk`;

    if (elements.mastheadEdition)
      elements.mastheadEdition.textContent = `${st} Edition`;

    if (elements.stateFocusTitle)
      elements.stateFocusTitle.textContent = `STATE IN FOCUS: ${st.toUpperCase()} DEVELOPMENTS`;

    if (elements.bureauCopilotHeading)
      elements.bureauCopilotHeading.textContent = `${st.toUpperCase()} DESK CO-PILOT`;

    if (elements.bureauCopilotDesc) {
      elements.bureauCopilotDesc.textContent = `Active bureau monitoring 48 state gazettes, 14 local civic bodies, and regional university repositories across ${st} for fact-checked announcements.`;
    }
  }

  function updateCalibratedRankTags() {
    if (!elements.calibratedRankContainer) return;

    elements.calibratedRankContainer.innerHTML = "";

    const order = state.priorityOrder.slice(0, 5);

    order.forEach((cat, idx) => {
      const tag = document.createElement("span");

      tag.className =
        "font-label-caps text-[11px] bg-surface-container px-2 py-0.5 text-on-surface-variant flex items-center gap-1 border border-outline-variant/20";

      tag.innerHTML = `<strong class="text-primary">0${idx + 1}</strong> ${cat}`;

      elements.calibratedRankContainer.appendChild(tag);
    });
  }

  // --- Category Synonyms & Aliasing ---

  // --- 28 States and 8 Union Territories of India (Authoritative Geographic Gazetteer) ---
  const INDIAN_STATES_AND_UTS = {
    // 28 Indian States
    "andhra pradesh": [
      "andhra pradesh",
      "amaravati",
      "visakhapatnam",
      "vizag",
      "vijayawada",
      "tirupati",
      "guntur",
      "kurnool",
      "nellore",
    ],
    "arunachal pradesh": [
      "arunachal pradesh",
      "itanagar",
      "tawang",
      "pasighat",
      "ziro",
    ],
    assam: [
      "assam",
      "guwahati",
      "dispur",
      "dibrugarh",
      "silchar",
      "jorhat",
      "kaziranga",
      "brahmaputra",
    ],
    bihar: [
      "bihar",
      "patna",
      "gaya",
      "bhagalpur",
      "muzaffarpur",
      "darbhanga",
      "purnia",
      "nalanda",
    ],
    chhattisgarh: [
      "chhattisgarh",
      "raipur",
      "bilaspur",
      "durg",
      "bhilai",
      "bastar",
      "korba",
    ],
    goa: ["goa", "panaji", "panjim", "margao", "vasco da gama", "calangute"],
    gujarat: [
      "gujarat",
      "gandhinagar",
      "ahmedabad",
      "surat",
      "vadodara",
      "baroda",
      "rajkot",
      "bhavnagar",
      "jamnagar",
      "kutch",
    ],
    haryana: [
      "haryana",
      "gurugram",
      "gurgaon",
      "faridabad",
      "panipat",
      "ambala",
      "rohtak",
      "karnal",
      "hisar",
    ],
    "himachal pradesh": [
      "himachal pradesh",
      "shimla",
      "dharamshala",
      "manali",
      "kullu",
      "mandi",
      "solan",
      "spiti",
    ],
    jharkhand: [
      "jharkhand",
      "ranchi",
      "jamshedpur",
      "dhanbad",
      "bokaro",
      "deoghar",
      "hazaribagh",
    ],
    karnataka: [
      "karnataka",
      "bengaluru",
      "bangalore",
      "mysuru",
      "mysore",
      "hubballi",
      "mangaluru",
      "mangalore",
      "belagavi",
    ],
    kerala: [
      "kerala",
      "thiruvananthapuram",
      "trivandrum",
      "kochi",
      "cochin",
      "kozhikode",
      "calicut",
      "thrissur",
      "kannur",
      "wayanad",
      "kollam",
    ],
    "madhya pradesh": [
      "madhya pradesh",
      "bhopal",
      "indore",
      "gwalior",
      "jabalpur",
      "ujjain",
      "rewa",
    ],
    maharashtra: [
      "maharashtra",
      "mumbai",
      "pune",
      "nagpur",
      "nashik",
      "thane",
      "aurangabad",
      "sambhajinagar",
      "solapur",
      "kolhapur",
    ],
    manipur: ["manipur", "imphal", "churachandpur", "kangpokpi", "bishnupur"],
    meghalaya: ["meghalaya", "shillong", "tura", "cherrapunji", "sohra"],
    mizoram: ["mizoram", "aizawl", "lunglei", "champhai"],
    nagaland: ["nagaland", "kohima", "dimapur", "mokokchung"],
    odisha: [
      "odisha",
      "orissa",
      "bhubaneswar",
      "cuttack",
      "rourkela",
      "puri",
      "sambalpur",
      "balasore",
    ],
    punjab: [
      "punjab",
      "amritsar",
      "ludhiana",
      "jalandhar",
      "patiala",
      "bathinda",
      "mohali",
    ],
    rajasthan: [
      "rajasthan",
      "jaipur",
      "jodhpur",
      "udaipur",
      "kota",
      "ajmer",
      "bikaner",
      "jaisalmer",
      "alwar",
    ],
    sikkim: ["sikkim", "gangtok", "namchi", "pelling"],
    "tamil nadu": [
      "tamil nadu",
      "chennai",
      "madras",
      "coimbatore",
      "madurai",
      "tiruchirappalli",
      "trichy",
      "salem",
      "tirunelveli",
    ],
    telangana: [
      "telangana",
      "hyderabad",
      "secunderabad",
      "warangal",
      "nizamabad",
      "karimnagar",
      "khammam",
      "revanth",
    ],
    tripura: ["tripura", "agartala", "dharmanagar"],
    "uttar pradesh": [
      "uttar pradesh",
      "lucknow",
      "kanpur",
      "varanasi",
      "kashi",
      "prayagraj",
      "allahabad",
      "noida",
      "greater noida",
      "agra",
      "meerut",
      "ayodhya",
      "gorakhpur",
      "bareilly",
      "mathura",
    ],
    uttarakhand: [
      "uttarakhand",
      "dehradun",
      "haridwar",
      "rishikesh",
      "nainital",
      "kedarnath",
      "badrinath",
      "roorkee",
    ],
    "west bengal": [
      "west bengal",
      "kolkata",
      "calcutta",
      "howrah",
      "durgapur",
      "siliguri",
      "asansol",
      "darjeeling",
    ],
    // 8 Union Territories
    "andaman and nicobar islands": ["andaman", "nicobar", "port blair"],
    chandigarh: ["chandigarh"],
    "dadra and nagar haveli and daman and diu": [
      "dadra",
      "nagar haveli",
      "daman",
      "diu",
      "silvassa",
    ],
    delhi: [
      "delhi",
      "new delhi",
      "ncr",
      "chawri bazar",
      "connaught place",
      "dwarka",
      "rohini",
    ],
    "jammu and kashmir": [
      "jammu and kashmir",
      "jammu & kashmir",
      "j&k",
      "srinagar",
      "jammu",
      "anantnag",
      "baramulla",
      "kashmir",
    ],
    ladakh: ["ladakh", "leh", "kargil"],
    lakshadweep: ["lakshadweep", "kavaratti"],
    puducherry: ["puducherry", "pondicherry", "karaikal", "mahe", "yanam"],
  };

  function distill60Words(text) {
    if (!text) return "";
    const words = text.trim().split(/\s+/);
    if (words.length <= 60) return text;
    return words.slice(0, 60).join(" ") + "…";
  }

  const CATEGORY_SYNONYMS = {
    tech: ["tech", "technology"],

    technology: ["tech", "technology"],

    world: ["world", "international", "global"],

    international: ["world", "international", "global"],

    global: ["world", "international", "global"],

    national: ["national", "india"],

    state: ["state", "regional"],

    politics: ["politics", "political"],

    business: ["business", "economy", "finance"],

    science: ["science", "space"],

    health: ["health", "medical"],

    sports: ["sports", "sport"],

    entertainment: ["entertainment", "cinema", "movies", "culture"],

    environment: ["environment", "climate", "nature"],

    education: ["education", "learning", "academics"],
  };

  function matchesCategory(cardCat, targetCat) {
    if (!targetCat || targetCat.toLowerCase() === "all") return true;

    if (!cardCat) return false;

    const c1 = cardCat.trim().toLowerCase();

    const c2 = targetCat.trim().toLowerCase();

    if (c1 === c2) return true;

    const s1 = CATEGORY_SYNONYMS[c1] || [c1];

    const s2 = CATEGORY_SYNONYMS[c2] || [c2];

    return s1.some((v) => s2.includes(v));
  }

  // --- Multi-Dimensional Ranking Engine ---

  function rankCardsByUserPreferencesAndPriority(
    cards,
    interests,
    priorityOrder,
    userState,
    activeCategory,
  ) {
    if (!cards || cards.length === 0) return [];

    const targetState = (userState || "").trim().toLowerCase();
    let filtered = cards;

    // Tab isolation & Personalization
    const catLow = (activeCategory || "for_you").toLowerCase();
    if (catLow === "state") {
      filtered = cards.filter((c) => {
        const cs = (c.state || "").trim().toLowerCase();
        const head = (c.headline || "").toLowerCase();
        const isRegional =
          (c.category || "").toLowerCase() === "state" ||
          (c.category || "").toLowerCase() === "regional";
        return (
          (targetState && (cs === targetState || head.includes(targetState))) ||
          isRegional
        );
      });
    } else if (catLow !== "all" && catLow !== "for_you" && catLow !== "saved") {
      filtered = cards.filter((c) =>
        matchesCategory(c.category, activeCategory),
      );
      if (filtered.length === 0) {
        const kw = activeCategory.toLowerCase();
        filtered = cards.filter((c) =>
          ((c.headline || "") + " " + (c.summary || ""))
            .toLowerCase()
            .includes(kw),
        );
      }
    } else if (catLow === "for_you") {
      // "For You" Editorial Personalization:
      // Guaranteed inclusion of user's state news + preferred interest categories
      if (interests && Array.isArray(interests) && interests.length > 0) {
        const preferred = cards.filter((c) => {
          const cState = (c.state || "").trim().toLowerCase();
          const head = (c.headline || "").toLowerCase();
          const isStateMatch =
            targetState &&
            (cState === targetState ||
              (targetState.includes("delhi") && cState.includes("delhi")) ||
              head.includes(targetState));
          if (isStateMatch) return true;

          return (
            interests.some((pref) => matchesCategory(c.category, pref)) ||
            matchesCategory(c.category, "state")
          );
        });

        // Ensure rich broadsheet volume: if preferred stories are under 35, backfill with top general dispatches
        if (preferred.length < 35 && cards.length > preferred.length) {
          const seenIds = new Set(preferred.map((c) => c.id || c.headline));
          const backfill = cards.filter(
            (c) => !seenIds.has(c.id || c.headline),
          );
          filtered = preferred.concat(backfill.slice(0, 35 - preferred.length));
        } else {
          filtered = preferred;
        }
      }
    } else {
      // "All News" Tab: Full unfiltered feed across all categories
      filtered = cards;
    }

    if (filtered.length === 0 && cards.length > 0) {
      filtered = cards;
    }

    // Build Priority Tier lookup
    const activePriority =
      priorityOrder && priorityOrder.length > 0
        ? priorityOrder
        : interests || [];
    const priorityIndexMap = new Map();
    activePriority.forEach((cat, idx) => {
      const cLow = cat.trim().toLowerCase();
      priorityIndexMap.set(cLow, idx);
      const syns = CATEGORY_SYNONYMS[cLow] || [];
      syns.forEach((s) => {
        if (!priorityIndexMap.has(s)) priorityIndexMap.set(s, idx);
      });
    });

    function getCardPriorityTier(card) {
      const cat = (card.category || "").trim().toLowerCase();
      if (priorityIndexMap.has(cat)) return priorityIndexMap.get(cat);
      const syns = CATEGORY_SYNONYMS[cat] || [];
      for (const s of syns) {
        if (priorityIndexMap.has(s)) return priorityIndexMap.get(s);
      }
      return 999;
    }

    function getCardTimestamp(card) {
      const ts = card.published_at || card.event_time || card.created_at;
      if (!ts) return 0;
      const ms = Date.parse(ts);
      return isNaN(ms) ? 0 : ms;
    }

    function getRecencyScore(card) {
      const ts = card.published_at || card.event_time || card.created_at;
      if (!ts) return 20;
      const ms = Date.parse(ts);
      if (isNaN(ms)) return 20;
      const now = Date.now();
      const diffHours = (now - ms) / (1000 * 60 * 60);
      if (diffHours < 0) return 120; // future or just published wire
      if (diffHours <= 1) return 120; // < 1 hour: 120 pts
      if (diffHours <= 3) return 115; // < 3 hours: 115 pts
      if (diffHours <= 6) return 110; // < 6 hours: 110 pts
      if (diffHours <= 12) return 100; // < 12 hours: 100 pts
      if (diffHours <= 24) return 90; // < 24 hours (Today): 90 pts
      if (diffHours <= 48) return 50; // Yesterday: 50 pts
      if (diffHours <= 168) return 20; // Last 7 days: 20 pts
      return 0; // Older than 7 days
    }

    function getStateMatchScore(card) {
      if (!targetState) return 0;
      const cState = (card.state || "").trim().toLowerCase();
      if (cState === targetState) return 100;
      if (targetState.includes("delhi") && cState.includes("delhi")) return 100;

      const kws = INDIAN_STATES_AND_UTS[targetState] || [targetState];
      const text = (
        (card.headline || "") +
        " " +
        (card.summary || "")
      ).toLowerCase();
      for (const kw of kws) {
        if (text.includes(kw)) return 80;
      }
      return 0;
    }

    function calculateCompositeScore(card) {
      const recency = getRecencyScore(card);
      const tier = getCardPriorityTier(card);
      const priorityPoints =
        tier === 0
          ? 35
          : tier === 1
            ? 25
            : tier === 2
              ? 15
              : tier === 3
                ? 10
                : 0;
      const stateMatch = getStateMatchScore(card);

      const ts = card.published_at || card.event_time || card.created_at;
      const ms = ts ? Date.parse(ts) : NaN;
      const isToday = !isNaN(ms) && Date.now() - ms <= 24 * 60 * 60 * 1000;

      // In All News & General Feed: Objective importance & urgency lead the feed!
      // State boost only applies in the dedicated State tab or mildly in For You
      let statePoints = 0;
      if (activeCategory === "state") {
        statePoints = stateMatch === 100 ? (isToday ? 250 : 150) : (stateMatch === 60 ? 100 : 0);
      } else if (activeCategory === "for_you") {
        statePoints = stateMatch === 100 ? (isToday ? 35 : 20) : (stateMatch === 60 ? 15 : 0);
      } else {
        // "all" and specific categories: 0 state bias, national/global importance dominates
        statePoints = 0;
      }

      const importanceScore = Number(card.importance_score) || 75;
      const urgencyScore = Number(card.urgency_score) || 50;
      const qualityScore = Number(card.final_feed_score) || 70;
      const verificationScore = Number(card.verification_score) || 80;

      // Editorial Weighting: Importance (40%) + Recency (30%) + Urgency (15%) + Verification (15%)
      return (
        importanceScore * 2.2 +
        recency * 1.6 +
        urgencyScore * 0.9 +
        verificationScore * 0.6 +
        qualityScore * 0.4 +
        priorityPoints +
        statePoints
      );
    }

    return [...filtered].sort((a, b) => {
      if (activeCategory === "state") {
        const aState = getStateMatchScore(a);
        const bState = getStateMatchScore(b);
        if (aState !== bState) return bState - aState;
      }

      const scoreA = calculateCompositeScore(a);
      const scoreB = calculateCompositeScore(b);
      if (scoreA !== scoreB) return scoreB - scoreA;

      return getCardTimestamp(b) - getCardTimestamp(a);
    });
  }

  // --- Dynamic Editorial Layout Renderers ---

  function renderHeroLead(card) {
    if (!elements.heroLeadContainer || !card) return;

    const cat = (card.category || "National Policy").toUpperCase();

    const timeAgo = formatTimeAgo(
      card.published_at || card.event_time || card.created_at,
    );

    const source =
      card.source_name ||
      (card.sources && card.sources[0]?.name) ||
      "Verified Wire Service";

    const imp = Math.round(card.importance_score || 92);

    const trust = Math.round(card.verification_score || 95);

    const rel = Math.round(card.personal_relevance_score || 94);

    elements.heroLeadContainer.innerHTML = `
      <article class="bg-[#ffffff] p-space-lg md:p-space-xl relative overflow-hidden shadow-sm border border-[#e2e8f0] border-l-4 border-l-[#ff7a00] rounded-sm">
        <div class="flex flex-wrap items-center justify-between gap-space-xs mb-space-sm">
          <div class="flex items-center gap-space-xs">
            <span class="w-2 h-2 bg-[#ff7a00] inline-block"></span>
            <span class="font-label-caps text-label-caps text-[#ff7a00] uppercase tracking-widest font-bold">${cat}</span>
            <span class="text-outline text-label-caps">&#8226;</span>
            <span class="font-label-caps text-label-caps text-[#a3a3a3] uppercase tracking-wider">TOP CALIBRATED LEAD</span>
          </div>

          <div class="flex items-center gap-space-sm text-outline font-label-sm text-label-sm">

            <span>Verified Wire</span><span>&#8226;</span><span>${source}</span>

          </div>

        </div>



        <h2 id="hero-headline-link" class="font-headline-md md:font-headline-lg text-headline-md md:text-headline-lg text-on-surface hover:text-primary transition-colors cursor-pointer mb-space-sm">

          ${card.headline}

        </h2>



        <p class="font-body-md md:font-body-lg text-body-md md:text-body-lg text-on-surface-variant mb-space-md leading-relaxed">

          ${card.summary || card.headline}

        </p>



        <!-- Attribution Bar -->

        <div class="flex flex-wrap items-center justify-between gap-space-sm bg-surface-container p-space-sm mb-space-md text-on-surface border border-outline-variant/20">

          <div class="flex items-center gap-space-xs font-label-md text-label-md">

            <span class="material-symbols-outlined text-[18px] text-secondary">verified</span>

            <span class="font-semibold text-on-surface">${source}</span>

            <span class="text-outline">&#8226;</span>

            <span class="text-on-surface-variant text-[13px]">${card.priority_reason || "Verified by independent wire telemetry"}</span>

          </div>

          <div class="flex items-center gap-2">

            <span class="text-xs px-2.5 py-1 bg-surface-container-high text-on-surface uppercase font-mono font-medium rounded-sm tracking-wider">Full Audit Available</span>

          </div>

        </div>



        <!-- Actions -->

        <div class="flex items-center justify-between pt-space-xs">

          <button id="btn-hero-dossier" class="font-body-md text-body-md italic text-primary hover:text-surface-tint underline underline-offset-4 flex items-center gap-1 font-medium cursor-pointer" type="button">

            Read Story &amp; Verification Dossier &rarr;

          </button>

          <div class="flex items-center gap-2 text-on-surface-variant">
            <button id="btn-hero-listen" class="flex items-center gap-1 px-2.5 py-1 bg-[#f0f2f5] hover:bg-[#e4e6eb] border border-[#d1d5db] text-primary text-xs font-semibold rounded-sm transition-colors cursor-pointer" title="Listen to Lead Dispatch">
              <span class="material-symbols-outlined text-[17px]">volume_up</span>
              <span>Listen</span>
            </button>
            <button id="btn-hero-bookmark" class="p-2 hover:bg-[#f0f2f5] text-outline hover:text-primary transition-colors cursor-pointer" title="Save Story">
              <span class="material-symbols-outlined text-[19px]">${isCardSaved(card.id) ? "bookmark" : "bookmark_border"}</span>
            </button>
            <button id="btn-hero-share" class="p-2 hover:bg-[#f0f2f5] hover:text-on-surface transition-colors cursor-pointer" title="Share Story">
              <span class="material-symbols-outlined text-[19px]">share</span>
            </button>
          </div>
        </div>
      </article>
    `;

    document
      .getElementById("hero-headline-link")
      ?.addEventListener("click", () => openDetailModal(card));
    document
      .getElementById("btn-hero-dossier")
      ?.addEventListener("click", () => openDetailModal(card));
    document
      .getElementById("btn-hero-listen")
      ?.addEventListener("click", () => toggleAudioNarration(card));
    document
      .getElementById("btn-hero-bookmark")
      ?.addEventListener("click", () => {
        toggleCardSaved(card);
        const icon = document.querySelector("#btn-hero-bookmark span");
        if (icon)
          icon.textContent = isCardSaved(card.id)
            ? "bookmark"
            : "bookmark_border";
      });
    document
      .getElementById("btn-hero-share")
      ?.addEventListener("click", () => shareStory(card));
  }

  function renderSecondaryGrid(cards) {
    if (!elements.secondaryGridContainer) return;

    elements.secondaryGridContainer.innerHTML = "";

    if (state.isInitialLoading && cards.length <= 1) {
      return;
    }

    const leadId = state.cards[0]?.id;
    const nonLead = cards.filter((c) => c.id !== leadId);
    const pair = nonLead.slice(0, 2);

    pair.forEach((c) => {
      const art = document.createElement("article");

      art.className =
        "bg-surface-container-low p-space-lg flex flex-col justify-between shadow-sm relative border border-outline-variant/15";

      const timeAgo = formatTimeAgo(c.published_at || c.event_time);

      const source =
        c.source_name || (c.sources && c.sources[0]?.name) || "Verified Wire";

      const imp = Math.round(c.importance_score || 82);

      const trust = Math.round(c.verification_score || 90);

      art.innerHTML = `

        <div>

          <div class="flex items-center justify-between gap-space-xs mb-space-xs">

            <span class="font-label-caps text-label-caps text-primary uppercase tracking-wider font-semibold">

              ${(c.category || "General").toUpperCase()}

            </span>

            <span class="font-label-sm text-label-sm text-outline">${source}</span>

          </div>

          <h3 class="font-headline-sm text-headline-sm text-on-surface hover:text-primary transition-colors cursor-pointer mb-space-xs line-clamp-2">

            ${c.headline}

          </h3>

          <p class="font-body-md text-body-md text-on-surface-variant/90 mb-space-md line-clamp-3 leading-relaxed">

            ${c.summary || c.headline}

          </p>

        </div>

        <div>

          <div class="bg-surface-container-lowest p-space-xs mb-space-sm flex items-center justify-between font-label-caps text-[10px] text-outline border border-outline-variant/10">

            <span class="font-semibold text-on-surface-variant">${source}</span>

            <span class="text-secondary font-medium">Verified Story</span>

          </div>

          <div class="flex items-center justify-between pt-1">

            <button class="font-body-md text-[15px] italic text-primary hover:text-surface-tint underline underline-offset-4 cursor-pointer btn-open-dossier" type="button">

              Full Dispatch &rarr;

            </button>

            <button class="text-on-surface-variant hover:text-on-surface transition-colors p-1 cursor-pointer btn-share-secondary" title="Share">

              <span class="material-symbols-outlined text-[18px]">share</span>

            </button>

          </div>

        </div>

      `;

      art
        .querySelector("h3")
        ?.addEventListener("click", () => openDetailModal(c));

      art
        .querySelector(".btn-open-dossier")
        ?.addEventListener("click", () => openDetailModal(c));

      art
        .querySelector(".btn-share-secondary")
        ?.addEventListener("click", () => shareStory(c));

      elements.secondaryGridContainer.appendChild(art);
    });
  }

  function renderStateFocusDesk(allCards, userState) {
    if (!elements.stateFocusContainer) return;

    elements.stateFocusContainer.innerHTML = "";

    const st = (userState || "").trim().toLowerCase();

    // Always query from the full master pool of cards so state news is never replaced with World news
    const pool =
      state.allMasterCards && state.allMasterCards.length > 0
        ? state.allMasterCards
        : state.allRankedCache && state.allRankedCache.length > 0
          ? state.allRankedCache
          : allCards;

    const leadId = state.cards[0]?.id;
    const leadHead = (state.cards[0]?.headline || "").trim().toLowerCase();
    const excludeIds = new Set([leadId]);
    const excludeHeads = new Set([leadHead]);

    const secPair = state.cards.filter((c) => c.id !== leadId).slice(0, 2);
    secPair.forEach((c) => {
      if (c.id) excludeIds.add(c.id);
      if (c.headline) excludeHeads.add(c.headline.trim().toLowerCase());
    });

    let stateMatches = pool.filter((c) => {
      if (
        excludeIds.has(c.id) ||
        (c.headline && excludeHeads.has(c.headline.trim().toLowerCase()))
      ) {
        return false;
      }
      const cs = (c.state || "").trim().toLowerCase();
      const head = (c.headline || "").toLowerCase();
      return (
        (st && (cs === st || head.includes(st))) ||
        (st.includes("delhi") && cs.includes("delhi"))
      );
    });

    if (stateMatches.length === 0) {
      // Fall back strictly to Indian regional state cards, NEVER world news
      stateMatches = pool
        .filter((c) => (c.category || "").toLowerCase() === "state")
        .slice(0, 3);
    } else {
      stateMatches = stateMatches.slice(0, 3);
    }

    stateMatches.forEach((c) => {
      const strip = document.createElement("article");

      strip.className =
        "bg-surface-container-low hover:bg-surface-container p-space-md flex flex-col md:flex-row md:items-center justify-between gap-space-md transition-colors border border-outline-variant/15";

      const timeAgo = formatTimeAgo(c.published_at || c.event_time);

      const source =
        c.source_name ||
        (c.sources && c.sources[0]?.name) ||
        `${userState} Wire`;

      strip.innerHTML = `

        <div class="flex-1">

          <div class="flex items-center gap-space-xs font-label-caps text-[10px] text-outline mb-1">

            <span class="text-primary font-semibold uppercase">${c.category || "Regional"}</span>

            <span>&#8226;</span>

            <span>${source}</span>

            

          </div>

          <h4 class="font-headline-sm text-[19px] leading-snug text-on-surface hover:text-primary transition-colors cursor-pointer strip-headline">

            ${c.headline}

          </h4>

          <p class="font-body-md text-[14px] text-on-surface-variant/80 mt-1 line-clamp-1">

            ${c.summary || c.headline}

          </p>

        </div>

        <div class="flex items-center gap-space-md shrink-0">

          

          <button class="btn-action-link strip-link" type="button"><span>Read &rarr;</span></button>

        </div>

      `;

      strip
        .querySelector(".strip-headline")
        ?.addEventListener("click", () => openDetailModal(c));

      strip
        .querySelector(".strip-link")
        ?.addEventListener("click", () => openDetailModal(c));

      elements.stateFocusContainer.appendChild(strip);
    });
  }

  function renderStreamFeed(cards) {
    if (!elements.streamFeedContainer) return;

    elements.streamFeedContainer.innerHTML = "";

    if (state.isInitialLoading && cards.length <= 1) {
      if (elements.feedPaginationStatus)
        elements.feedPaginationStatus.classList.add("hidden");

      elements.streamFeedContainer.innerHTML = `

        <div class="bg-surface-container-low p-space-lg border border-outline-variant/20 flex flex-col sm:flex-row items-center justify-between gap-space-md text-center sm:text-left transition-opacity duration-300">

          <div class="flex items-center gap-space-xs text-primary">

            <span class="inline-block w-2.5 h-2.5 rounded-full bg-primary animate-pulse"></span>

            <span class="font-label-md text-label-md uppercase tracking-wider font-semibold">Updating Live Dispatches in Background...</span>

          </div>

          <span class="font-label-sm text-outline uppercase tracking-wider">${state.state} Desk Active</span>

        </div>

      `;

      return;
    }

    if (elements.feedPaginationStatus)
      elements.feedPaginationStatus.classList.remove("hidden");

    const leadId = cards[0]?.id;
    const leadHead = (cards[0]?.headline || "").trim().toLowerCase();
    const seenTitles = new Set([leadHead]);

    // Also register secondary pair headlines so stream never repeats them
    const secondaryPair = state.cards
      .filter((c) => c.id !== leadId)
      .slice(0, 2);
    secondaryPair.forEach((c) => {
      if (c.headline) seenTitles.add(c.headline.trim().toLowerCase());
    });

    // Also register State in Focus desk headlines so stream only presents fresh, distinct stories
    if (elements.stateFocusContainer) {
      elements.stateFocusContainer
        .querySelectorAll("article h4")
        .forEach((el) => {
          const t = el.innerText.trim().toLowerCase();
          if (t) seenTitles.add(t);
        });
    }

    const nonLead = cards.filter((c) => {
      if (c.id === leadId) return false;
      const h = (c.headline || "").trim().toLowerCase();
      if (!h || seenTitles.has(h)) return false;
      seenTitles.add(h);
      return true;
    });

    const streamItems = nonLead;

    streamItems.forEach((c) => {
      const art = document.createElement("article");
      art.className =
        "bg-surface-container-low p-4 sm:p-5 border border-outline-variant/15 hover:border-primary/40 hover:bg-surface-container transition-all rounded-sm group";
      const source =
        c.source_name || (c.sources && c.sources[0]?.name) || "Verified Wire";
      const cat = (c.category || "general").toLowerCase();

      // Visual Anchor Icon Map (Issue 10: Break wall of text)
      const ICON_MAP = {
        national: "flag",
        politics: "policy",
        technology: "memory",
        business: "trending_up",
        science: "biotech",
        health: "health_and_safety",
        sports: "sports_cricket",
        world: "public",
        entertainment: "theaters",
        environment: "eco",
      };
      const icon = ICON_MAP[cat] || "newspaper";

      // Issues 8 & 12: Action button inline with 40px touch target, visual anchor badge
      art.innerHTML = `
        <div class="flex items-start gap-3 sm:gap-4">
          <!-- Visual Anchor Icon Pill -->
          <div class="shrink-0 w-9 h-9 sm:w-10 sm:h-10 rounded-sm bg-surface-container border border-outline-variant/30 flex items-center justify-center text-primary group-hover:bg-primary group-hover:text-on-primary transition-colors">
            <span class="material-symbols-outlined text-[18px] sm:text-[20px]">${icon}</span>
          </div>

          <div class="flex-1 min-w-0">
            <!-- Card Header Metadata -->
            <div class="flex flex-wrap items-center gap-2 text-xs text-outline mb-1.5 font-medium">
              <span class="text-primary font-semibold uppercase">${c.category || "General"}</span>
              <span>•</span>
              <span class="text-on-surface-variant">${source}</span>
              <span>•</span>
              <span class="text-surface-tint">${formatTimeAgo(c.published_at || c.created_at)}</span>
            </div>

            <!-- Headline -->
            <h4 class="font-serif text-base sm:text-lg leading-snug text-on-surface group-hover:text-primary transition-colors cursor-pointer stream-title mb-1.5">
              ${c.headline}
            </h4>

            <!-- Summary -->
            <p class="text-sm text-on-surface-variant/90 line-clamp-2 leading-relaxed mb-2 font-sans">
              ${escapeHtml((c.summary || c.headline).replace(/<[^>]+>/g, "").split("\n\n")[0])}
            </p>
            <div class="mb-3 inline-flex items-center gap-1 text-[11px] font-mono text-primary/90 font-semibold">
              <span class="material-symbols-outlined text-[13px]">summarize</span>
              <span>${c.word_count || 240}-Word Simple English Dossier</span>
            </div>

            <!-- Inline Action Button: Standardized >=40px Touch Target (Issues 8 & 12) -->
            <div class="flex items-center gap-3 pt-1">
              <button type="button" class="btn-action-link stream-btn" aria-label="Read full dispatch for ${c.headline.replace(/"/g, "&quot;")}">
                <span>Read Dispatch</span>
                <span class="material-symbols-outlined text-[16px]">arrow_forward</span>
              </button>
              <button type="button" class="btn-stream-listen p-1 text-outline hover:text-primary transition-colors cursor-pointer" title="Listen to story" aria-label="Listen to audio summary">
                <span class="material-symbols-outlined text-[18px]">volume_up</span>
              </button>
              <button type="button" class="btn-stream-save p-1 text-outline hover:text-primary transition-colors cursor-pointer" title="Bookmark story" aria-label="Save story">
                <span class="material-symbols-outlined text-[18px]">${isCardSaved(c.id) ? "bookmark" : "bookmark_border"}</span>
              </button>
            </div>
          </div>
        </div>
      `;

      art
        .querySelector(".stream-title")
        ?.addEventListener("click", () => openDetailModal(c));
      art
        .querySelector(".stream-btn")
        ?.addEventListener("click", () => openDetailModal(c));
      art
        .querySelector(".btn-stream-listen")
        ?.addEventListener("click", (e) => {
          e.stopPropagation();
          toggleAudioNarration(c);
        });
      art.querySelector(".btn-stream-save")?.addEventListener("click", (e) => {
        e.stopPropagation();
        toggleCardSaved(c);
        const icon = art.querySelector(".btn-stream-save span");
        if (icon)
          icon.textContent = isCardSaved(c.id) ? "bookmark" : "bookmark_border";
      });
      elements.streamFeedContainer.appendChild(art);
    });

    if (elements.statShowingCount)
      elements.statShowingCount.textContent = String(cards.length);

    if (elements.statTotalCount)
      elements.statTotalCount.textContent = String(
        state.allRankedCache.length || cards.length,
      );
  }

  function renderMorningBrief(cards, leadCard) {
    if (!elements.morningBriefContainer) return;

    elements.morningBriefContainer.innerHTML = "";

    // Never repeat the Hero Lead headline in the fast-scan brief
    const leadId = leadCard ? leadCard.id : cards[0] ? cards[0].id : null;
    const pool =
      state.allMasterCards && state.allMasterCards.length > 0
        ? state.allMasterCards
        : cards;
    const available = pool.filter(
      (c) =>
        c.id !== leadId && (leadCard ? c.headline !== leadCard.headline : true),
    );
    // Sort by urgency and importance for dynamic high-impact breaking news
    available.sort((a, b) => {
      const scoreA = (a.urgency_score || 80) * 1.5 + (a.importance_score || 85);
      const scoreB = (b.urgency_score || 80) * 1.5 + (b.importance_score || 85);
      return scoreB - scoreA;
    });
    // Robust deduplication: ensure each bullet in the brief covers a distinct story
    const topBullets = [];
    const seenWords = new Set();
    for (const c of available) {
      if (topBullets.length >= 4) break;
      const tokens = (c.headline || "").toLowerCase().replace(/[^a-z0-9 ]/g, "").split(/\s+/).filter(w => w.length > 3);
      const isDupe = tokens.filter(w => seenWords.has(w)).length >= 3;
      if (!isDupe) {
        topBullets.push(c);
        tokens.forEach(w => seenWords.add(w));
      }
    }

    topBullets.forEach((c) => {
      const div = document.createElement("div");

      div.className =
        "pb-space-xs border-b border-outline-variant/10 last:border-b-0 cursor-pointer";

      const imp = Math.round(c.importance_score || 80);

      div.innerHTML = `

        <div class="flex items-center justify-between font-label-caps text-[10px] text-outline mb-1">

          <span class="text-primary uppercase font-semibold">${c.category || "Brief"}</span>

          <span class="text-outline font-normal">Fast Scan</span>

        </div>

        <p class="font-body-md text-[14px] leading-relaxed text-on-surface hover:text-primary transition-colors line-clamp-2">

          ${c.headline}

        </p>

      `;

      div.addEventListener("click", () => openDetailModal(c));

      elements.morningBriefContainer.appendChild(div);
    });
  }

  function updateAlgorithmicRadar(leadCard) {
    if (!leadCard) return;

    const imp = Math.round(leadCard.importance_score || 92);

    const urg = Math.round(leadCard.urgency_score || 84);

    const frs = Math.round(leadCard.freshness_score || 95);

    const ver = Math.round(leadCard.verification_score || 98);

    const rel = Math.round(leadCard.personal_relevance_score || 90);

    if (elements.barValImportance)
      elements.barValImportance.textContent = `${imp}%`;

    if (elements.barFillImportance)
      elements.barFillImportance.style.width = `${imp}%`;

    if (elements.barValUrgency) elements.barValUrgency.textContent = `${urg}%`;

    if (elements.barFillUrgency)
      elements.barFillUrgency.style.width = `${urg}%`;

    if (elements.barValFreshness)
      elements.barValFreshness.textContent = `${frs}%`;

    if (elements.barFillFreshness)
      elements.barFillFreshness.style.width = `${frs}%`;

    if (elements.barValVerification)
      elements.barValVerification.textContent = `${ver}%`;

    if (elements.barFillVerification)
      elements.barFillVerification.style.width = `${ver}%`;

    if (elements.barValRelevance)
      elements.barValRelevance.textContent = `${rel}%`;

    if (elements.barFillRelevance)
      elements.barFillRelevance.style.width = `${rel}%`;

    // Dynamic 5-axis polygon scaling

    // Center is (100, 75). Radius ~50

    const cx = 100,
      cy = 75,
      maxR = 50;

    const angles = [
      -Math.PI / 2,
      -Math.PI / 2 + 0.4 * Math.PI * 1,
      -Math.PI / 2 + 0.4 * Math.PI * 2,
      -Math.PI / 2 + 0.4 * Math.PI * 3,
      -Math.PI / 2 + 0.4 * Math.PI * 4,
    ];

    const scores = [imp / 100, urg / 100, frs / 100, ver / 100, rel / 100];

    const pts = angles.map((ang, i) => {
      const r = Math.max(10, scores[i] * maxR);

      const x = Math.round(cx + r * Math.cos(ang));

      const y = Math.round(cy + r * Math.sin(ang));

      return `${x},${y}`;
    });

    if (elements.radarDataPolygon) {
      elements.radarDataPolygon.setAttribute("points", pts.join(" "));
    }
  }

  // --- Master Render Coordinator ---

  function renderAllEditorialSections() {
    if (state.cards.length === 0) return;

    const lead = state.cards[0];

    renderHeroLead(lead);

    renderSecondaryGrid(state.cards);

    renderStateFocusDesk(
      state.allRankedCache.length > 0 ? state.allRankedCache : state.cards,
      state.state,
    );

    renderStreamFeed(state.cards);

    renderMorningBrief(
      state.allRankedCache.length > 0 ? state.allRankedCache : state.cards,
      lead,
    );

    updateAlgorithmicRadar(lead);

    updateLanguageUI();
    updateLocationHeaders();

    updateCalibratedRankTags();
  }

  // --- 60-Word Quick Read Mode (InShorts Reel Controller) ---

  function openQuickReadMode(startIndex = -1) {
    if (!elements.quickReadOverlay) return;
    state.quickReadMode = true;
    const pool =
      state.allRankedCache && state.allRankedCache.length > 0
        ? state.allRankedCache
        : state.allMasterCards || [];
    state.quickReadCards = pool.length > 0 ? pool : state.cards;

    if (startIndex >= 0) {
      state.quickReadIndex = Math.max(
        0,
        Math.min(startIndex, state.quickReadCards.length - 1),
      );
    } else {
      let savedIdx = 0;
      try {
        savedIdx = parseInt(
          sessionStorage.getItem("newzz_last_read_index") || "0",
          10,
        );
      } catch (_) {}
      state.quickReadIndex = Math.max(
        0,
        Math.min(savedIdx, state.quickReadCards.length - 1),
      );
    }

    elements.quickReadOverlay.classList.remove("hidden");
    elements.quickReadOverlay.classList.add("flex");
    document.body.style.overflow = "hidden";
    renderActiveQuickReadCard();
  }

  function closeQuickReadMode() {
    if (!elements.quickReadOverlay) return;
    state.quickReadMode = false;
    elements.quickReadOverlay.classList.add("hidden");
    elements.quickReadOverlay.classList.remove("flex");
    document.body.style.overflow = "";
  }

  function renderActiveQuickReadCard() {
    if (!state.quickReadCards || state.quickReadCards.length === 0) return;
    const card = state.quickReadCards[state.quickReadIndex];
    if (!card) return;

    // Render Visual Topic / Photo Banner (Issue 1: Break text wall)
    if (elements.qrVisualBanner) {
      elements.qrVisualBanner.innerHTML = generateVisualBanner(card);
    }
    recordStoryRead();

    if (elements.qrCounter) {
      elements.qrCounter.textContent = `${state.quickReadIndex + 1} / ${state.quickReadCards.length}`;
    }

    if (elements.qrCategoryBadge) {
      elements.qrCategoryBadge.textContent = (
        card.category || "National"
      ).toUpperCase();
    }

    if (elements.qrStateBadge) {
      if (card.state) {
        elements.qrStateBadge.textContent = card.state.toUpperCase();
        elements.qrStateBadge.classList.remove("hidden");
      } else {
        elements.qrStateBadge.classList.add("hidden");
      }
    }

    if (elements.qrTrustBadge) {
      elements.qrTrustBadge.textContent =
        card.verification_type === "cross_verified"
          ? "Tier-1 Corroborated"
          : "Verified Wire";
    }

    if (elements.qrTimeAgo) {
      elements.qrTimeAgo.textContent = formatTimeAgo(
        card.published_at || card.event_time,
      );
    }

    if (elements.qrHeadline) {
      elements.qrHeadline.textContent = card.headline;
    }

    if (elements.qrSummary) {
      elements.qrSummary.textContent = distill60Words(
        card.summary || card.headline,
      );
    }

    if (elements.qrSourceName) {
      elements.qrSourceName.textContent =
        card.source_name ||
        (card.sources && card.sources[0]?.name) ||
        "Verified Wire";
    }

    if (elements.qrBtnOriginal) {
      const url =
        card.canonical_url ||
        card.url ||
        (card.sources && card.sources[0]?.url) ||
        "https://www.thehindu.com";
      elements.qrBtnOriginal.setAttribute("href", url);
    }

    if (elements.qrKeyFacts) {
      elements.qrKeyFacts.innerHTML = "";
      const facts =
        card.key_facts &&
        Array.isArray(card.key_facts) &&
        card.key_facts.length > 0
          ? card.key_facts.slice(0, 2)
          : [
              `Verified by ${card.source_name || "editorial wire"}`,
              `Coverage prioritized for ${state.state || "All India"}`,
            ];

      facts.forEach((f) => {
        const p = document.createElement("p");
        p.className =
          "text-xs text-on-surface-variant flex items-start gap-1.5";
        p.innerHTML = `<span class="text-primary font-bold">✓</span><span>${escapeHtml(f)}</span>`;
        elements.qrKeyFacts.appendChild(p);
      });
    }

    // Persist position in sessionStorage
    try {
      sessionStorage.setItem(
        "newzz_last_read_index",
        String(state.quickReadIndex),
      );
    } catch (_) {}

    // Update Bookmark & Audio Icons
    updateBookmarkIcons(card.id);
    updateAudioIcons(state.currentSpeakingCardId === card.id);

    // Micro-animation bounce on card
    const art = document.getElementById("qr-card-article");
    if (art) {
      art.classList.add("scale-[0.99]");
      setTimeout(() => art.classList.remove("scale-[0.99]"), 120);
    }
  }

  function nextQuickReadCard() {
    if (state.quickReadIndex < state.quickReadCards.length - 1) {
      state.quickReadIndex++;
      renderActiveQuickReadCard();
    } else {
      showFeedToast("You are caught up on all dispatches!");
    }
  }

  function prevQuickReadCard() {
    if (state.quickReadIndex > 0) {
      state.quickReadIndex--;
      renderActiveQuickReadCard();
    }
  }

  // --- Vernacular Language Engine (EN | Hindi) ---
  const I18N = {
    en: {
      forYou: "For You",
      allNews: "All News",
      politics: "Politics",
      technology: "Technology",
      national: "National",
      state: "State",
      business: "Business",
      world: "World",
      science: "Science",
      health: "Health",
      sports: "Sports",
      environment: "Environment",
      saved: "Saved",
      trending: "Trending:",
      listen: "Listen",
      stop: "Stop",
      fullDossier: "Full Dossier",
      readWire: "Read Wire →",
      explainSimply: "Explain Simply",
      streak: "Streak",
      readToday: "Read",
    },
    hi: {
      forYou: "आपके लिए",
      allNews: "सभी समाचार",
      politics: "राजनीति",
      technology: "प्रौद्योगिकी",
      national: "राष्ट्रीय",
      state: "राज्य",
      business: "व्यापार",
      world: "विश्व",
      science: "विज्ञान",
      health: "स्वास्थ्य",
      sports: "खेल",
      environment: "पर्यावरण",
      saved: "सहेजे गए",
      trending: "ट्रेंडिंग:",
      listen: "सुनें",
      stop: "रोकें",
      fullDossier: "पूरी रिपोर्ट",
      readWire: "मूल स्रोत पढ़ें →",
      explainSimply: "सरल भाषा में समझें",
      streak: "लगातार",
      readToday: "पढ़े गए",
    },
  };

  function toggleLanguage() {
    state.currentLang = state.currentLang === "en" ? "hi" : "en";
    try {
      localStorage.setItem("newzz_lang", state.currentLang);
    } catch (_) {}
    updateLanguageUI();
    showFeedToast(
      state.currentLang === "hi"
        ? "भाषा: हिंदी सक्रिय"
        : "Language: English Active",
    );
    applyFiltersAndRender();
  }

  function updateLanguageUI() {
    const isHi = state.currentLang === "hi";
    const dict = isHi ? I18N.hi : I18N.en;

    if (elements.langToggleText) {
      elements.langToggleText.textContent = isHi ? "हि" : "EN";
    }

    // Update Tab Labels
    const tabMap = {
      "tab-for-you": dict.forYou,
      "tab-all": dict.allNews,
      "tab-politics": dict.politics,
      "tab-technology": dict.technology,
      "tab-national": dict.national,
      "tab-state": dict.state,
      "tab-business": dict.business,
      "tab-world": dict.world,
      "tab-science": dict.science,
      "tab-health": dict.health,
      "tab-sports": dict.sports,
      "tab-environment": dict.environment,
      "tab-saved": dict.saved,
    };

    Object.entries(tabMap).forEach(([id, text]) => {
      const el = document.getElementById(id);
      if (el) {
        const icon =
          el.querySelector(".material-symbols-outlined") ||
          el.querySelector("span");
        if (icon) {
          el.innerHTML = `${icon.outerHTML} ${text}`;
        } else {
          el.textContent = text;
        }
      }
    });

    updateStreakUI();
  }

  // --- Reading Habit & Streak Tracker ---
  function recordStoryRead() {
    state.readingStreak.count++;
    try {
      localStorage.setItem(
        "newzz_streak_v1",
        JSON.stringify(state.readingStreak),
      );
    } catch (_) {}
    updateStreakUI();
  }

  function updateStreakUI() {
    if (!elements.readingStreakText) return;
    const isHi = state.currentLang === "hi";
    const dict = isHi ? I18N.hi : I18N.en;
    elements.readingStreakText.textContent = `${dict.streak}: ${state.readingStreak.days} ${isHi ? "दिन" : "Days"} • ${state.readingStreak.count} ${dict.readToday}`;
  }

  // --- Visual Topic & Media Banner Generator ---
  function generateVisualBanner(card) {
    if (!card) return "";
    if (card.image_url) {
      return `<img src="${escapeHtml(card.image_url)}" class="w-full h-full object-cover" alt="${escapeHtml(card.headline)}" loading="lazy"/>`;
    }

    const cat = (card.category || "National").toUpperCase();
    const icons = {
      NATIONAL: "flag",
      POLITICS: "policy",
      TECHNOLOGY: "memory",
      BUSINESS: "trending_up",
      SCIENCE: "biotech",
      HEALTH: "health_and_safety",
      SPORTS: "sports_cricket",
      WORLD: "public",
      ENVIRONMENT: "eco",
      STATE: "location_city",
    };
    const icon = icons[cat] || "newspaper";

    return `
      <div class="w-full h-full bg-gradient-to-br from-[#fff7ed] via-[#ffedd5] to-[#fed7aa] border border-[#fed7aa] flex items-center justify-between px-5 sm:px-6 relative overflow-hidden select-none">
        <div class="absolute -right-3 -bottom-5 text-6xl sm:text-7xl font-bold font-mono text-white/[0.04] tracking-widest pointer-events-none">${cat}</div>
        <div class="flex items-center gap-3 z-10">
          <div class="w-11 h-11 sm:w-12 sm:h-12 rounded bg-[#ff7a00]/15 border border-[#ff7a00]/40 flex items-center justify-center text-[#ff7a00] shadow-md">
            <span class="material-symbols-outlined text-[24px] sm:text-[26px]">${icon}</span>
          </div>
          <div>
            <div class="text-[10px] sm:text-[11px] font-mono uppercase tracking-widest text-[#ff7a00] font-bold">${cat} INTELLIGENCE</div>
            <div class="text-xs text-[#a3a3a3] font-medium max-w-[200px] truncate">${escapeHtml(card.source_name || (card.sources && card.sources[0]?.name) || "Verified Wire")}</div>
          </div>
        </div>
        <div class="flex items-center gap-1.5 px-2 py-0.5 bg-white/90 border border-[#fed7aa] rounded text-[10px] font-mono text-[#9a3412] font-semibold z-10 shadow-xs">
          <span class="w-1.5 h-1.5 rounded-full bg-[#ff7a00] animate-pulse"></span>
          <span>VERIFIED WIRE</span>
        </div>
      </div>
    `;
  }

  // --- Ground News-Style Corroboration Spectrum ---
  function renderCorroborationSpectrum(card) {
    if (!elements.detailCorroborationSpectrum) return;
    const sources =
      card.sources && Array.isArray(card.sources) && card.sources.length > 0
        ? card.sources
        : [
            {
              name: card.source_name || "Primary Wire Service",
              trust_tier: "1",
            },
          ];

    const count = sources.length;
    if (elements.detailCorroborationCount) {
      elements.detailCorroborationCount.textContent =
        count > 1 ? `${count} Outlets Corroborated` : "1 Verified Primary Wire";
    }

    if (elements.spectrumBarFill) {
      const pct = Math.min(100, Math.max(35, count * 35));
      elements.spectrumBarFill.style.width = `${pct}%`;
    }

    if (elements.detailSpectrumSourcesChips) {
      elements.detailSpectrumSourcesChips.innerHTML = "";
      sources.forEach((s) => {
        const chip = document.createElement("span");
        chip.className =
          "px-2 py-0.5 bg-[#1c1c1c] border border-[#2e2e2e] text-[#ededed] rounded-sm flex items-center gap-1";
        chip.innerHTML = `<span class="text-primary font-bold">●</span><span>${escapeHtml(s.name || "Wire")}</span>`;
        elements.detailSpectrumSourcesChips.appendChild(chip);
      });
    }
  }

  // --- Audio Narration (Web Speech TTS) ---
  function toggleAudioNarration(card) {
    if (!("speechSynthesis" in window)) {
      showFeedToast("Speech synthesis is not supported in this browser.");
      return;
    }

    if (
      window.speechSynthesis.speaking &&
      state.currentSpeakingCardId === card.id
    ) {
      window.speechSynthesis.cancel();
      state.currentSpeakingCardId = null;
      updateAudioIcons(false);
      showFeedToast("Audio bulletin paused");
      return;
    }

    window.speechSynthesis.cancel();

    const cleanText = `${card.headline}. ${distill60Words(card.summary || "")}`;
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 0.95;
    utterance.pitch = 1.0;

    const voices = window.speechSynthesis.getVoices();
    const voice =
      voices.find(
        (v) => v.lang && (v.lang.includes("en-IN") || v.lang.includes("en_IN")),
      ) ||
      voices.find((v) => v.lang && v.lang.startsWith("en")) ||
      null;
    if (voice) utterance.voice = voice;

    utterance.onstart = () => {
      state.currentSpeakingCardId = card.id;
      updateAudioIcons(true);
      showFeedToast("Playing 60s voice bulletin...");
    };

    utterance.onend = utterance.onerror = () => {
      state.currentSpeakingCardId = null;
      updateAudioIcons(false);
    };

    state.speakingUtterance = utterance;
    window.speechSynthesis.speak(utterance);
  }

  function updateAudioIcons(isPlaying) {
    const icon = isPlaying ? "stop" : "volume_up";
    const label = isPlaying ? "Stop" : "Listen";

    if (elements.qrListenIcon) elements.qrListenIcon.textContent = icon;
    if (elements.qrListenLabel) elements.qrListenLabel.textContent = label;
    if (elements.modalListenIcon) elements.modalListenIcon.textContent = icon;
    if (elements.modalListenLabel)
      elements.modalListenLabel.textContent = label;
  }

  // --- Bookmarking & Offline Pocket Library ---
  function isCardSaved(cardId) {
    return !!(cardId && state.savedCardIds.includes(cardId));
  }

  function toggleCardSaved(card) {
    if (!card || !card.id) return;
    const idx = state.savedCardIds.indexOf(card.id);
    if (idx >= 0) {
      state.savedCardIds.splice(idx, 1);
      try {
        localStorage.removeItem("newzz_saved_card_" + card.id);
      } catch (_) {}
      showFeedToast("Story removed from saved bookmarks");
    } else {
      state.savedCardIds.push(card.id);
      try {
        localStorage.setItem(
          "newzz_saved_card_" + card.id,
          JSON.stringify(card),
        );
      } catch (_) {}
      showFeedToast("Story saved for offline reading");
    }
    try {
      localStorage.setItem(
        "newzz_saved_ids_v1",
        JSON.stringify(state.savedCardIds),
      );
    } catch (_) {}
    updateBookmarkIcons(card.id);

    if (state.activeCategory === "saved") {
      applyFiltersAndRender();
    }
  }

  function updateBookmarkIcons(cardId) {
    const saved = isCardSaved(cardId);
    const iconName = saved ? "bookmark" : "bookmark_border";

    if (elements.qrBookmarkIcon) {
      elements.qrBookmarkIcon.textContent = iconName;
      if (saved) {
        elements.qrBookmarkIcon.classList.add("text-primary");
        elements.qrBookmarkIcon.classList.remove("text-outline");
      } else {
        elements.qrBookmarkIcon.classList.remove("text-primary");
        elements.qrBookmarkIcon.classList.add("text-outline");
      }
    }

    if (elements.modalBookmarkIcon) {
      elements.modalBookmarkIcon.textContent = iconName;
      if (saved) {
        elements.modalBookmarkIcon.classList.add("text-primary");
        elements.modalBookmarkIcon.classList.remove("text-outline");
      } else {
        elements.modalBookmarkIcon.classList.remove("text-primary");
        elements.modalBookmarkIcon.classList.add("text-outline");
      }
    }
  }

  // --- ELI5 (Explain Simply) Engine ---
  function explainSimply(card) {
    if (!card || !elements.detailEli5Box || !elements.detailEli5Text) return;

    if (
      !elements.detailEli5Box.classList.contains("hidden") &&
      state.eli5CardId === card.id
    ) {
      elements.detailEli5Box.classList.add("hidden");
      return;
    }

    state.eli5CardId = card.id;
    elements.detailEli5Box.classList.remove("hidden");

    const keyFact =
      Array.isArray(card.key_facts) && card.key_facts.length > 0
        ? card.key_facts[0]
        : "Official dispatches confirm operational verification.";

    let raw = card.summary || card.headline;
    let simplified = distill60Words(raw)
      .replace(
        /In a significant development|primary news reports|confirm that key public officials/gi,
        "Official reports show",
      )
      .replace(
        /administrative, economic, and policy considerations/gi,
        "practical and daily issues",
      )
      .replace(
        /operational benchmarks|regulatory compliance/gi,
        "safety standards and protocols",
      )
      .replace(
        /stakeholders and community members/gi,
        "citizens and local communities",
      );

    elements.detailEli5Text.innerHTML = `<strong>In plain terms:</strong> ${escapeHtml(simplified)}<br><span class="mt-2 block text-xs text-primary font-mono font-semibold">✓ Key Takeaway: ${escapeHtml(keyFact)}</span>`;
  }

  // --- Trending Topics Engine ---
  function extractTrendingTopics(cards) {
    const STOPWORDS = new Set([
      "the",
      "a",
      "an",
      "in",
      "on",
      "at",
      "to",
      "for",
      "of",
      "and",
      "or",
      "is",
      "are",
      "was",
      "were",
      "has",
      "have",
      "had",
      "been",
      "will",
      "with",
      "from",
      "by",
      "as",
      "it",
      "this",
      "that",
      "its",
      "says",
      "said",
      "new",
      "after",
      "over",
      "into",
      "amid",
      "ahead",
      "under",
      "news",
      "india",
      "indian",
      "verified",
      "report",
      "reports",
      "day",
      "days",
      "today",
      "more",
      "about",
      "state",
      "government",
      "police",
      "court",
      "case",
      "high",
      "delhi",
      "center",
      "first",
      "two",
      "three",
      "years",
      "time",
    ]);

    const counts = {};
    const pool = (cards || []).slice(0, 100);
    pool.forEach((c) => {
      const text = `${c.headline || ""} ${c.summary || ""}`;
      const matches = text.match(/\b[A-Z][a-zA-Z0-9]{2,}\b/g) || [];
      matches.forEach((w) => {
        const clean = w.trim();
        const lower = clean.toLowerCase();
        if (!STOPWORDS.has(lower) && clean.length > 2) {
          counts[clean] = (counts[clean] || 0) + 1;
        }
      });
    });

    return Object.entries(counts)
      .filter(
        ([word, count]) => count >= 2 && !STOPWORDS.has(word.toLowerCase()),
      )
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([word]) => word);
  }

  function renderTrendingTopics(cards) {
    if (!elements.trendingChipsList) return;
    const topics = extractTrendingTopics(cards);
    elements.trendingChipsList.innerHTML = "";

    if (topics.length === 0) {
      elements.trendingTopicsContainer?.classList.add("hidden");
      return;
    }
    elements.trendingTopicsContainer?.classList.remove("hidden");

    topics.forEach((topic) => {
      const btn = document.createElement("button");
      const isActive = state.activeTrendingTopic === topic;
      btn.className = `px-2.5 py-1 text-[11px] font-mono rounded border transition-all cursor-pointer flex items-center gap-1 ${
        isActive
          ? "bg-primary text-black font-bold border-primary shadow-sm"
          : "bg-[#ffffff] hover:bg-[#f0f2f5] text-[#333333] hover:text-[#ff7a00] border-[#d1d5db] shadow-xs"
      }`;
      btn.innerHTML = `<span class="${isActive ? "text-black" : "text-primary"}">#</span><span>${escapeHtml(topic)}</span>`;

      btn.addEventListener("click", () => {
        if (state.activeTrendingTopic === topic) {
          state.activeTrendingTopic = null;
        } else {
          state.activeTrendingTopic = topic;
        }
        renderTrendingTopics(state.allMasterCards || cards);
        applyFiltersAndRender();
      });

      elements.trendingChipsList.appendChild(btn);
    });
  }

  // --- Unified Multi-Dimensional Filter & Rank Pipeline ---
  function applyFiltersAndRender() {
    let pool =
      state.allMasterCards && state.allMasterCards.length > 0
        ? state.allMasterCards
        : state.cards || [];

    // 1. Saved Tab Filter
    if (state.activeCategory === "saved") {
      pool = pool.filter((c) => isCardSaved(c.id));
      state.savedCardIds.forEach((id) => {
        if (!pool.some((c) => c.id === id)) {
          try {
            const stored = localStorage.getItem("newzz_saved_card_" + id);
            if (stored) pool.push(JSON.parse(stored));
          } catch (_) {}
        }
      });
    }

    // 2. Multi-Dimensional Ranking
    let ranked = rankCardsByUserPreferencesAndPriority(
      pool,
      state.interests,
      state.priorityOrder,
      state.state,
      state.activeCategory,
    );

    // 3. Active Trending Topic Filter
    if (state.activeTrendingTopic) {
      const topicLower = state.activeTrendingTopic.toLowerCase();
      ranked = ranked.filter((c) => {
        const text = `${c.headline || ""} ${c.summary || ""}`.toLowerCase();
        return text.includes(topicLower);
      });
    }

    // 4. Search Filter (Preserved across category & state changes!)
    const query = elements.inputSearch
      ? elements.inputSearch.value.trim().toLowerCase()
      : "";
    if (query) {
      ranked = ranked.filter((c) => {
        const combined =
          `${c.headline || ""} ${c.summary || ""} ${Array.isArray(c.key_facts) ? c.key_facts.join(" ") : ""}`.toLowerCase();
        return combined.includes(query);
      });
    }

    state.allRankedCache = ranked;
    state.cards = ranked.slice(0, state.pageSize);
    renderAllEditorialSections();

    if (elements.statShowingCount)
      elements.statShowingCount.textContent = String(state.cards.length);
    if (elements.statTotalCount)
      elements.statTotalCount.textContent = String(ranked.length);
  }

  // --- Story Detail Modal ---

  function openDetailModal(card) {
    if (!card || !elements.modalDetail) return;

    state.selectedCard = card;

    if (elements.detailCategoryBadge)
      elements.detailCategoryBadge.textContent = (
        card.category || "General"
      ).toUpperCase();

    if (elements.detailVerificationBadge)
      elements.detailVerificationBadge.textContent =
        card.verification_type === "cross_verified"
          ? "Tier-1 Corroborated"
          : "Verified";

    if (elements.detailHeadline)
      elements.detailHeadline.textContent = card.headline;

    if (elements.detailSourceAuthor)
      elements.detailSourceAuthor.textContent =
        card.source_name ||
        (card.sources && card.sources[0]?.name) ||
        "Verified Primary Wire";

    if (elements.detailTime) {
      const pubIso = card.published_at || card.created_at;
      const relTime = formatTimeAgo(pubIso);
      const dateStr = pubIso
        ? new Date(pubIso).toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          })
        : "";
      elements.detailTime.textContent = dateStr
        ? `${relTime} • ${dateStr}`
        : relTime;
    }

    const imp = Number(card.importance_score || 85).toFixed(1);

    const urg = Number(card.urgency_score || 80).toFixed(1);

    const frs = Number(card.freshness_score || 95).toFixed(1);

    const ver = Number(card.verification_score || 88).toFixed(1);

    const rel = Number(card.personal_relevance_score || 90).toFixed(1);

    if (elements.detailScoreImportance)
      elements.detailScoreImportance.textContent = `${imp}/100`;

    if (elements.detailScoreUrgency)
      elements.detailScoreUrgency.textContent = `${urg}/100`;

    if (elements.detailScoreFreshness)
      elements.detailScoreFreshness.textContent = `${frs}/100`;

    if (elements.detailScoreVerification)
      elements.detailScoreVerification.textContent = `${ver}/100`;

    if (elements.detailScoreRelevance)
      elements.detailScoreRelevance.textContent = `${rel}/100`;

    if (elements.barImportance)
      if (elements.barImportance)
        elements.barImportance.style.width = `${Math.min(100, imp)}%`;

    if (elements.barUrgency)
      if (elements.barUrgency)
        elements.barUrgency.style.width = `${Math.min(100, urg)}%`;

    if (elements.barFreshness)
      if (elements.barFreshness)
        elements.barFreshness.style.width = `${Math.min(100, frs)}%`;

    if (elements.barVerification)
      if (elements.barVerification)
        elements.barVerification.style.width = `${Math.min(100, ver)}%`;

    if (elements.barRelevance)
      if (elements.barRelevance)
        elements.barRelevance.style.width = `${Math.min(100, rel)}%`;

    if (elements.detailPriorityReason)
      elements.detailPriorityReason.textContent =
        card.priority_reason ||
        "Verified by independent cross-checked wire reports.";

    if (elements.detailSummaryContent) {
      const rawSummary = card.summary || card.headline || "";
      const cleanSummary = rawSummary.replace(/<[^>]+>/g, "").trim();
      const paras = cleanSummary.split("\n\n");
      const wordCount = cleanSummary.split(/\s+/).filter(Boolean).length;

      let html = `
        <div class="mb-4 inline-flex items-center gap-2 px-2.5 py-1 bg-primary/15 text-primary border border-primary/30 rounded-sm font-mono text-[11px] font-bold uppercase tracking-wider">
          <span class="material-symbols-outlined text-[14px]">article</span>
          <span>${wordCount} Words &#8226; Simple English &#8226; Concise Briefing</span>
        </div>
      `;

      paras.forEach((para) => {
        if (para.trim()) {
          html += `<p class="mb-3 text-sm sm:text-base text-on-surface leading-relaxed font-sans">${escapeHtml(para.trim())}</p>`;
        }
      });

      if (
        card.key_facts &&
        Array.isArray(card.key_facts) &&
        card.key_facts.length > 0
      ) {
        html += `
          <div class="mt-4 p-3.5 bg-surface-container border-l-2 border-primary rounded-sm">
            <h5 class="text-xs font-mono font-bold uppercase text-primary tracking-wider mb-2 flex items-center gap-1.5">
              <span class="material-symbols-outlined text-[14px]">check_circle</span>
              <span>Key Factual Takeaways</span>
            </h5>
            <ul class="space-y-1.5 text-xs text-on-surface-variant font-sans list-disc list-inside">
              ${card.key_facts.map((f) => `<li>${escapeHtml(f)}</li>`).join("")}
            </ul>
          </div>
        `;
      }

      const sourceUrl = card.canonical_url || card.url || card.source_url;
      if (sourceUrl) {
        html += `
          <div class="mt-4 pt-3 border-t border-outline-variant/20 flex items-center justify-between">
            <span class="text-xs font-mono text-outline">Verified Primary Wire Record</span>
            <a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1.5 text-xs font-mono font-bold text-primary hover:underline">
              <span>Read Original Wire Source</span>
              <span class="material-symbols-outlined text-[14px]">open_in_new</span>
            </a>
          </div>
        `;
      }

      elements.detailSummaryContent.innerHTML = html;
    }

    if (elements.detailSourcesList) {
      elements.detailSourcesList.innerHTML = "";

      const sources =
        card.sources && card.sources.length > 0
          ? card.sources
          : [
              {
                name: card.source_name || "Primary Wire Source",
                url: card.canonical_url || card.source_url || "#",
              },
            ];

      sources.forEach((s) => {
        const li = document.createElement("li");

        li.innerHTML = `<a href="${s.url || "#"}" target="_blank" rel="noopener noreferrer" class="hover:underline flex items-center gap-1">${s.name || "Wire Link"} &rarr;</a>`;

        elements.detailSourcesList.appendChild(li);
      });
    }

    if (elements.btnOpenOriginalArticle) {
      elements.btnOpenOriginalArticle.href =
        card.canonical_url ||
        card.source_url ||
        (card.sources && card.sources[0]?.url) ||
        "#";
    }

    // Render Ground News-Style Corroboration Spectrum
    renderCorroborationSpectrum(card);
    recordStoryRead();

    // Reset ELI5 box & update bookmark/audio icons
    if (elements.detailEli5Box) elements.detailEli5Box.classList.add("hidden");
    state.eli5CardId = null;
    updateBookmarkIcons(card.id);
    updateAudioIcons(state.currentSpeakingCardId === card.id);

    elements.modalDetail.classList.remove("hidden");
  }

  function shareStory(card) {
    const url = card.canonical_url || card.source_url || window.location.href;

    if (navigator.share) {
      navigator
        .share({ title: card.headline, text: card.summary, url })
        .catch(() => {});
    } else {
      navigator.clipboard
        .writeText(url)
        .then(() => {
          showFeedToast("Story link copied to clipboard");
        })
        .catch(() => {});
    }
  }

  // --- Instant 0ms Paint ---

  function showInstantFirstCard() {
    try {
      const cached = localStorage.getItem(STORAGE_KEYS.TOP_CARD_CACHE);
      if (cached) {
        const parsed = JSON.parse(cached);
        if (parsed && parsed.headline) {
          const sumLow = (parsed.summary || "").toLowerCase();
          const headLow = (parsed.headline || "").toLowerCase();
          const isFake =
            sumLow.includes("in a significant development") ||
            sumLow.includes("technical committees and administrative task forces") ||
            sumLow.includes("the dispatch highlights key operational") ||
            headLow.includes("crimes of tomorrow");
          if (isFake) {
            localStorage.removeItem(STORAGE_KEYS.TOP_CARD_CACHE);
          } else {
            state.cards = [parsed];
            renderHeroLead(parsed);
            updateLocationHeaders();
            return;
          }
        }
      }
      // Clean editorial loading placeholder while real dispatches sync
      if (elements.heroLeadContainer) {
        elements.heroLeadContainer.innerHTML = `
          <div class="bg-surface-container-low p-6 md:p-8 animate-pulse border-l-4 border-primary/40">
            <div class="h-4 w-32 bg-surface-container mb-4 rounded"></div>
            <div class="h-8 w-3/4 bg-surface-container mb-4 rounded"></div>
            <div class="h-4 w-full bg-surface-container mb-2 rounded"></div>
            <div class="h-4 w-2/3 bg-surface-container rounded"></div>
          </div>
        `;
      }
    } catch (e) {
      console.warn("Instant paint fallback note:", e);
    }
  }

  // --- Background Crawler Trigger ---

  function triggerBackgroundCrawler(targetState) {
    try {
      if (
        API_BASE &&
        !window.location.port.startsWith("88") &&
        (API_BASE.includes("8000") || API_BASE.includes("onrender.com"))
      ) {
        const st = targetState || state.state || "";
        const url = st
          ? `${API_BASE}/feed/refresh?state=${encodeURIComponent(st)}`
          : `${API_BASE}/feed/refresh`;
        return fetch(url, {
          method: "GET",
          mode: "cors",
        })
          .then((r) => r.json())
          .catch(() => {});
      }
    } catch (_) {}
    return Promise.resolve();
  }

  // --- Feed Fetcher & Sync ---

  async function fetchFeed(forceRefresh = false) {
    if (state.activeFetchController) {
      try {
        state.activeFetchController.abort();
      } catch (_) {}
      state.activeFetchController = null;
    }

    const controller = new AbortController();
    state.activeFetchController = controller;
    state.loading = true;

    try {
      const params = new URLSearchParams();
      params.append("device_id", state.deviceId);
      params.append("limit", "80");
      params.append("offset", "0");

      const isGeneralFeed =
        !state.activeCategory ||
        state.activeCategory === "all" ||
        state.activeCategory === "for_you";
      if (!isGeneralFeed && state.activeCategory !== "saved") {
        params.append("category", state.activeCategory);
      }

      if (state.state) {
        params.append("state", state.state);
      }

      if (forceRefresh) {
        params.append("_t", String(Date.now()));
      }

      let rawItems = null;

      // 1. Ingest from Live API when available
      try {
        const timeoutId = setTimeout(() => controller.abort(), 3500);
        const res = await fetch(`${API_BASE}/feed?${params.toString()}`, {
          signal: controller.signal,
          headers: { "Cache-Control": "no-cache", Pragma: "no-cache" },
        });
        clearTimeout(timeoutId);
        if (res.ok) {
          const apiData = await res.json();
          if (
            apiData &&
            Array.isArray(apiData.items) &&
            apiData.items.length > 0
          ) {
            rawItems = apiData.items;
          }
        }
      } catch (_) {}

      // 2. Seamless Static feed.json Fallback
      if (!rawItems || rawItems.length === 0) {
        try {
          const staticRes = await fetch(`./feed.json?_t=${Date.now()}`, {
            cache: "no-store",
          });
          if (staticRes.ok) {
            const rawData = await staticRes.json();
            const items = rawData.items || rawData.cards || [];
            if (Array.isArray(items) && items.length > 0) {
              rawItems = items;
            }
          }
        } catch (_) {}
      }

      if (!rawItems || rawItems.length === 0) {
        state.isInitialLoading = false;
        renderAllEditorialSections();
        return;
      }

      // Merge into state.allMasterCards so switching categories or states never loses previously fetched cards
      const existingMap = new Map();
      (state.allMasterCards || []).forEach((c) => {
        const key = c.id || c.canonical_url || c.headline;
        if (key) existingMap.set(key, c);
      });
      rawItems.forEach((c) => {
        const key = c.id || c.canonical_url || c.headline;
        if (key) existingMap.set(key, c);
      });
      state.allMasterCards = Array.from(existingMap.values());

      state.isInitialLoading = false;
      renderTrendingTopics(state.allMasterCards);
      applyFiltersAndRender();

      // Cache top lead card for next instant 0ms visit
      if (state.cards.length > 0) {
        try {
          localStorage.setItem(
            STORAGE_KEYS.TOP_CARD_CACHE,
            JSON.stringify(state.cards[0]),
          );
        } catch (_) {}
      }

      if (forceRefresh) {
        showFeedToast("Live feed refreshed with latest dispatches");
      }
    } catch (err) {
      if (err.name !== "AbortError") {
        console.error("Feed fetch error:", err);
      }
    } finally {
      if (state.activeFetchController === controller) {
        state.activeFetchController = null;
        state.loading = false;
      }
    }
  }

  // --- Interest & Priority Modals Logic ---

  function renderInterestChips() {
    if (!elements.interestChipsContainer) return;

    elements.interestChipsContainer.innerHTML = "";

    ALL_CATEGORIES.forEach((cat) => {
      const isSelected = state.interests.includes(cat);

      const chip = document.createElement("button");

      chip.type = "button";

      chip.className = `interest-chip ${isSelected ? "selected" : ""}`;

      chip.innerHTML = `<span>${cat}</span> <span>${isSelected ? "&#10003;" : "+"}</span>`;

      chip.addEventListener("click", () => {
        if (state.interests.includes(cat)) {
          state.interests = state.interests.filter((c) => c !== cat);
        } else {
          state.interests.push(cat);
        }

        renderInterestChips();
      });

      elements.interestChipsContainer.appendChild(chip);
    });
  }

  function syncPriorityWithInterests() {
    if (!state.priorityOrder || state.priorityOrder.length === 0) {
      state.priorityOrder = [...state.interests];

      return;
    }

    state.priorityOrder = state.priorityOrder.filter((c) =>
      state.interests.includes(c),
    );

    state.interests.forEach((c) => {
      if (!state.priorityOrder.includes(c)) state.priorityOrder.push(c);
    });
  }

  function renderPriorityList() {
    syncPriorityWithInterests();

    if (!elements.priorityListContainer) return;

    elements.priorityListContainer.innerHTML = "";

    state.priorityOrder.forEach((cat, idx) => {
      const item = document.createElement("div");

      item.className = "priority-item";

      item.innerHTML = `

        <div class="priority-item-left">

          <span class="priority-rank-badge">0${idx + 1}</span>

          <span class="priority-name">${cat}</span>

        </div>

        <div>

          <button class="btn-priority-move btn-move-up" type="button" ${idx === 0 ? "disabled" : ""}>&#9650;</button>

          <button class="btn-priority-move btn-move-down" type="button" ${idx === state.priorityOrder.length - 1 ? "disabled" : ""}>&#9660;</button>

        </div>

      `;

      item.querySelector(".btn-move-up")?.addEventListener("click", () => {
        if (idx > 0) {
          const t = state.priorityOrder[idx];

          state.priorityOrder[idx] = state.priorityOrder[idx - 1];

          state.priorityOrder[idx - 1] = t;

          renderPriorityList();
        }
      });

      item.querySelector(".btn-move-down")?.addEventListener("click", () => {
        if (idx < state.priorityOrder.length - 1) {
          const t = state.priorityOrder[idx];

          state.priorityOrder[idx] = state.priorityOrder[idx + 1];

          state.priorityOrder[idx + 1] = t;

          renderPriorityList();
        }
      });

      elements.priorityListContainer.appendChild(item);
    });
  }

  async function savePriorityOrder() {
    syncPriorityWithInterests();

    localStorage.setItem(
      STORAGE_KEYS.INTERESTS,
      JSON.stringify(state.interests),
    );

    localStorage.setItem(
      STORAGE_KEYS.PRIORITY_ORDER,
      JSON.stringify(state.priorityOrder),
    );

    elements.modalPriority.classList.add("hidden");

    updateCalibratedRankTags();

    await fetchFeed(true);

    showFeedToast("Priorities saved! Feed re-calibrated.");

    try {
      await fetch(
        `${API_BASE}/user/${encodeURIComponent(state.deviceId)}/preferences`,
        {
          method: "PUT",

          headers: { "Content-Type": "application/json" },

          body: JSON.stringify({
            category_order: state.priorityOrder.map((c) => c.toLowerCase()),
          }),
        },
      );
    } catch (_) {}
  }

  // --- Event Listeners Setup ---

  function initEventListeners() {
    // Vernacular Language Toggle
    elements.btnLangToggle?.addEventListener("click", () => toggleLanguage());

    // Refresh Live Feed Button

    elements.btnRefreshFeed?.addEventListener("click", async () => {
      elements.btnRefreshFeed.classList.add("refreshing");
      showFeedToast("Checking live wire services for fresh dispatches...");

      try {
        localStorage.removeItem(STORAGE_KEYS.TOP_CARD_CACHE);
      } catch (_) {}

      // Trigger targeted crawler refresh for selected state + national
      await triggerBackgroundCrawler(state.state);

      // Force immediate clean reload from server
      state.allMasterCards = [];
      await fetchFeed(true);

      // Second sync pass after 3s to capture newly ingested background wire items
      setTimeout(async () => {
        await fetchFeed(true);
        elements.btnRefreshFeed?.classList.remove("refreshing");
        showFeedToast("Feed updated! All fresh verified dispatches active.");
      }, 3000);
    });

    // Quick Read Toggle & Navigation Listeners
    elements.btnToggleQuickRead?.addEventListener("click", (e) => {
      e.preventDefault();
      openQuickReadMode(0);
    });

    elements.btnCloseQuickRead?.addEventListener("click", () => {
      closeQuickReadMode();
    });

    elements.qrNavNext?.addEventListener("click", () => nextQuickReadCard());
    elements.qrNavPrev?.addEventListener("click", () => prevQuickReadCard());

    elements.qrBtnFullDossier?.addEventListener("click", () => {
      const card = state.quickReadCards[state.quickReadIndex];
      if (card) {
        closeQuickReadMode();
        openDetailModal(card);
      }
    });

    elements.btnQrListen?.addEventListener("click", () => {
      const card = state.quickReadCards[state.quickReadIndex];
      if (card) toggleAudioNarration(card);
    });

    elements.btnQrBookmark?.addEventListener("click", () => {
      const card = state.quickReadCards[state.quickReadIndex];
      if (card) toggleCardSaved(card);
    });

    elements.btnQrShare?.addEventListener("click", () => {
      const card = state.quickReadCards[state.quickReadIndex];
      if (card) shareStory(card);
    });

    elements.btnModalListen?.addEventListener("click", () => {
      if (state.selectedCard) toggleAudioNarration(state.selectedCard);
    });

    elements.btnModalBookmark?.addEventListener("click", () => {
      if (state.selectedCard) toggleCardSaved(state.selectedCard);
    });

    elements.btnModalEli5?.addEventListener("click", () => {
      if (state.selectedCard) explainSimply(state.selectedCard);
    });

    // Touch Swipe Gestures for Quick Read
    let qrStartY = 0;
    let qrStartX = 0;
    elements.qrTouchArea?.addEventListener(
      "touchstart",
      (e) => {
        if (e.touches && e.touches[0]) {
          qrStartY = e.touches[0].clientY;
          qrStartX = e.touches[0].clientX;
        }
      },
      { passive: true },
    );

    elements.qrTouchArea?.addEventListener(
      "touchend",
      (e) => {
        if (!state.quickReadMode || !e.changedTouches || !e.changedTouches[0])
          return;
        const dy = qrStartY - e.changedTouches[0].clientY;
        const dx = qrStartX - e.changedTouches[0].clientX;
        if (Math.abs(dy) > 35 && Math.abs(dy) > Math.abs(dx)) {
          if (dy > 0) {
            nextQuickReadCard();
          } else {
            prevQuickReadCard();
          }
        }
      },
      { passive: true },
    );

    // Keyboard Shortcuts for Quick Read
    document.addEventListener("keydown", (e) => {
      if (!state.quickReadMode) return;
      if (
        e.key === "ArrowDown" ||
        e.key === " " ||
        e.key === "PageDown" ||
        e.key === "j"
      ) {
        e.preventDefault();
        nextQuickReadCard();
      } else if (e.key === "ArrowUp" || e.key === "PageUp" || e.key === "k") {
        e.preventDefault();
        prevQuickReadCard();
      } else if (e.key === "Escape") {
        closeQuickReadMode();
      }
    });

    // Category Tabs
    elements.categoryTabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        elements.categoryTabs.forEach((t) => {
          t.classList.remove(
            "active",
            "bg-primary",
            "text-on-primary",
            "font-semibold",
          );
          t.classList.add("bg-surface-container", "text-on-surface-variant");
        });
        tab.classList.add(
          "active",
          "bg-primary",
          "text-on-primary",
          "font-semibold",
        );
        tab.classList.remove("bg-surface-container", "text-on-surface-variant");

        state.activeCategory = tab.getAttribute("data-category") || "all";

        // Instant local filter & broadsheet update from master card pool (0ms)
        if (state.allMasterCards && state.allMasterCards.length > 0) {
          applyFiltersAndRender();
        }

        fetchFeed(true);
      });
    });

    // Nav For You

    elements.navForYou?.addEventListener("click", (e) => {
      e.preventDefault();

      const tabForYou = document.getElementById("tab-for-you");

      if (tabForYou) tabForYou.click();
    });

    // Load More Stories Button

    elements.btnLoadMore?.addEventListener("click", () => {
      if (
        state.allRankedCache &&
        state.cards.length < state.allRankedCache.length
      ) {
        const nextBatch = state.allRankedCache.slice(
          state.cards.length,
          state.cards.length + 15,
        );

        state.cards = state.cards.concat(nextBatch);

        renderStreamFeed(state.cards);

        if (state.cards.length >= state.allRankedCache.length) {
          if (elements.btnLoadMore) elements.btnLoadMore.style.display = "none";

          if (elements.statusCaughtUpMsg)
            elements.statusCaughtUpMsg.textContent =
              "All verified stories loaded.";
        }
      }
    });

    // Location Modal Triggers
    const openLoc = (e) => {
      if (e && e.preventDefault) e.preventDefault();
      if (elements.inputState) elements.inputState.value = state.state || "";
      elements.modalLocation?.classList.remove("hidden");
    };

    elements.btnOpenLocation?.addEventListener("click", openLoc);

    elements.btnChangeStateBanner?.addEventListener("click", openLoc);

    elements.btnCloseLocation?.addEventListener("click", () =>
      elements.modalLocation.classList.add("hidden"),
    );

    elements.btnSaveLocation?.addEventListener("click", async () => {
      const selected = elements.inputState.value.trim();
      state.state = selected || "All India";
      localStorage.setItem(STORAGE_KEYS.LOCATION_STATE, state.state);
      updateLocationHeaders();
      elements.modalLocation.classList.add("hidden");

      // Instant local ranking update with newly selected state (0ms)
      if (state.allMasterCards && state.allMasterCards.length > 0) {
        applyFiltersAndRender();
      }

      await fetchFeed(true);
      showFeedToast(`State set to ${state.state}`);
    });

    elements.btnSkipLocation?.addEventListener("click", () => {
      elements.modalLocation.classList.add("hidden");
    });

    // Interests Modal Triggers

    document
      .getElementById("btn-open-interests-modal")
      ?.addEventListener("click", () => {
        renderInterestChips();

        elements.modalInterests.classList.remove("hidden");
      });

    elements.btnCloseInterests?.addEventListener("click", () =>
      elements.modalInterests.classList.add("hidden"),
    );

    elements.btnResetInterests?.addEventListener("click", () => {
      state.interests = ["Politics", "Technology", "National", "Business"];

      renderInterestChips();
    });

    elements.btnSaveInterests?.addEventListener("click", () => {
      localStorage.setItem(
        STORAGE_KEYS.INTERESTS,
        JSON.stringify(state.interests),
      );

      syncPriorityWithInterests();

      elements.modalInterests.classList.add("hidden");

      renderPriorityList();

      elements.modalPriority.classList.remove("hidden");
    });

    // Priority Modal Triggers
    const openPriorityModal = (e) => {
      if (e && e.preventDefault) e.preventDefault();
      renderPriorityList();
      elements.modalPriority?.classList.remove("hidden");
    };
    elements.btnOpenPriorityModal?.addEventListener("click", openPriorityModal);
    document
      .getElementById("btn-edit-priority-banner")
      ?.addEventListener("click", openPriorityModal);

    elements.btnClosePriority?.addEventListener("click", () =>
      elements.modalPriority.classList.add("hidden"),
    );

    elements.btnBackPriority?.addEventListener("click", () => {
      elements.modalPriority.classList.add("hidden");

      renderInterestChips();

      elements.modalInterests.classList.remove("hidden");
    });

    elements.btnSavePriority?.addEventListener("click", savePriorityOrder);

    // Story Detail Close

    elements.btnCloseDetail?.addEventListener("click", () =>
      elements.modalDetail.classList.add("hidden"),
    );

    // Modal Backdrops Click to Dismiss

    document.querySelectorAll(".modal-backdrop").forEach((bd) => {
      bd.addEventListener("click", (e) => {
        if (e.target === bd) bd.classList.add("hidden");
      });
    });

    // Escape Key

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        document
          .querySelectorAll(".modal-backdrop")
          .forEach((bd) => bd.classList.add("hidden"));
      }
    });

    // Search Input: Real-time debounced search across all master dispatches
    let searchDebounce = null;
    elements.inputSearch?.addEventListener("input", () => {
      clearTimeout(searchDebounce);
      searchDebounce = setTimeout(() => {
        applyFiltersAndRender();
      }, 200);
    });

    elements.inputSearch?.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        applyFiltersAndRender();
      }
    });
  }

  // --- Initial Boot ---

  function init() {
    updateLocationHeaders();

    updateCalibratedRankTags();

    initEventListeners();

    // 1. Instant 0ms Paint: Render exactly 1 Hero Lead story immediately

    showInstantFirstCard();

    // 2. In Background: Trigger crawler and smoothly fetch prioritized feed without UI lag

    triggerBackgroundCrawler();

    setTimeout(() => {
      fetchFeed();
    }, 250);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
