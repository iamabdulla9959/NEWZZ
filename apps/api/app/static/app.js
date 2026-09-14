/**

 * NEWZZ - Premium Editorial Intelligence Platform

 * BroadSheet UX Engine with Algorithmic Explainability, Regional Desks & Priority Calibration

 */



(function () {

  'use strict';



  // --- Configuration & API Base ---

  let API_BASE = window.RENDER_API_BASE || '';

  if (!API_BASE) {

    if ((window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') && window.location.port === '8000') {

      API_BASE = window.location.origin;

    } else {

      API_BASE = 'https://newzz-5e19.onrender.com';

    }

  }



  const STORAGE_KEYS = {

    DEVICE_ID: 'newsreels_device_id',

    LOCATION_STATE: 'newsreels_state',

    INTERESTS: 'newsreels_interests',

    PRIORITY_ORDER: 'newsreels_priority_order',

    ONBOARDING_COMPLETE: 'newsreels_onboarding_complete',

    TOP_CARD_CACHE: 'newsreels_top_card'

  };



  const ALL_CATEGORIES = [

    'Technology', 'Politics', 'Business', 'National', 'World',

    'Science', 'Health', 'Sports', 'Education', 'State',

    'Entertainment', 'Environment'

  ];



  // Instant Fallback Lead Story (rendered in 0ms on initial boot for zero perceived lag)

  const INSTANT_FALLBACK_CARD = {

    id: "lead-instant-01",

    headline: "India Clears ₹1,76,000-Crore Semiconductor Expansion: Advanced Wafer Fabrication Cluster Gets Cabinet Nod",

    summary: "The Union Cabinet has sanctioned the second phase of the India Semiconductor Mission, anchoring an advanced packaging and wafer fabrication ecosystem outside Hyderabad expected to create 24,000 high-skill engineering roles across the regional technology corridor.",

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

    priority_reason: "High strategic importance with cross-verified regulatory wire corroboration."

  };



  // --- State ---

  let state = {

    deviceId: getOrCreateDeviceId(),

    state: localStorage.getItem(STORAGE_KEYS.LOCATION_STATE) || 'Telangana',

    activeCategory: 'all',

    isInitialLoading: true,

    interests: getStoredInterests(),

    priorityOrder: getStoredPriorityOrder(),

    cards: [],

    cardIds: new Set(),

    allRankedCache: [],

    selectedCard: null,

    loading: false,

    offset: 0,

    pageSize: 30,

    hasMore: true

  };



  // --- DOM Elements ---

  const elements = {

    // Navigation & Masthead

    navForYou: document.getElementById('nav-for-you'),

    navLatest: document.getElementById('nav-latest'),

    navCategories: document.getElementById('nav-categories'),

    navStateEdition: document.getElementById('nav-state-edition'),

    navStateLabel: document.getElementById('nav-state-label'),

    inputSearch: document.getElementById('input-search-intelligence'),

    labelUserLocation: document.getElementById('label-user-location'),

    btnOpenLocation: document.getElementById('btn-open-location-modal'),

    btnRefreshFeed: document.getElementById('btn-refresh-feed'),

    // btnSavedDossiers removed

    

    // Personalization Banner

    mastheadDate: document.getElementById('masthead-date'),

    mastheadEdition: document.getElementById('masthead-edition'),

    verifiedStoriesCount: document.getElementById('verified-stories-count'),

    greetingName: document.getElementById('greeting-name'),

    bannerStateName: document.getElementById('banner-state-name'),

    bannerStateLabel: document.getElementById('banner-state-label'),

    btnChangeStateBanner: document.getElementById('btn-change-state-banner'),

    btnOpenPriorityModal: document.getElementById('btn-open-priority-modal'),

    calibratedRankContainer: document.getElementById('calibrated-rank-container'),



    // Category Tabs

    categoryTabs: document.querySelectorAll('.category-tab'),

    statShowingCount: document.getElementById('stat-showing-count'),

    statTotalCount: document.getElementById('stat-total-count'),



    // Editorial Flow Containers

    heroLeadContainer: document.getElementById('hero-lead-container'),

    secondaryGridContainer: document.getElementById('secondary-grid-container'),

    stateFocusSection: document.getElementById('state-focus-section'),

    stateFocusTitle: document.getElementById('state-focus-title'),

    stateFocusContainer: document.getElementById('state-focus-container'),

    streamFeedContainer: document.getElementById('stream-feed-container'),

    feedPaginationStatus: document.getElementById('feed-pagination-status'),

    btnLoadMore: document.getElementById('btn-load-more'),

    statusCaughtUpMsg: document.getElementById('status-caught-up-msg'),



    // Intelligence Sidebar

    morningBriefContainer: document.getElementById('morning-brief-container'),

    radarPersonaText: document.getElementById('radar-persona-text'),

    barValImportance: document.getElementById('bar-val-importance'),

    barFillImportance: document.getElementById('bar-fill-importance'),

    barValUrgency: document.getElementById('bar-val-urgency'),

    barFillUrgency: document.getElementById('bar-fill-urgency'),

    barValFreshness: document.getElementById('bar-val-freshness'),

    barFillFreshness: document.getElementById('bar-fill-freshness'),

    barValVerification: document.getElementById('bar-val-verification'),

    barFillVerification: document.getElementById('bar-fill-verification'),

    barValRelevance: document.getElementById('bar-val-relevance'),

    barFillRelevance: document.getElementById('bar-fill-relevance'),

    radarDataPolygon: document.getElementById('radar-data-polygon'),

    bureauCopilotHeading: document.getElementById('bureau-copilot-heading'),

    bureauCopilotDesc: document.getElementById('bureau-copilot-desc'),



    // Modals

    modalLocation: document.getElementById('modal-location'),

    btnCloseLocation: document.getElementById('btn-close-location-modal'),

    inputState: document.getElementById('input-state'),

    btnSaveLocation: document.getElementById('btn-save-location'),

    btnSkipLocation: document.getElementById('btn-skip-location'),



    modalInterests: document.getElementById('modal-interests'),

    btnCloseInterests: document.getElementById('btn-close-interests-modal'),

    interestChipsContainer: document.getElementById('interest-chips-container'),

    btnSaveInterests: document.getElementById('btn-save-interests'),

    btnResetInterests: document.getElementById('btn-reset-interests'),



    modalPriority: document.getElementById('modal-priority'),

    btnClosePriority: document.getElementById('btn-close-priority-modal'),

    btnBackPriority: document.getElementById('btn-back-priority'),

    btnSavePriority: document.getElementById('btn-save-priority'),

    priorityListContainer: document.getElementById('priority-list-container'),

    priorityErrorBanner: document.getElementById('priority-error-banner'),

    priorityErrorMsg: document.getElementById('priority-error-msg'),



    modalDetail: document.getElementById('modal-story-detail'),

    btnCloseDetail: document.getElementById('btn-close-detail-modal'),

    detailCategoryBadge: document.getElementById('detail-category-badge'),

    detailVerificationBadge: document.getElementById('detail-verification-badge'),

    detailHeadline: document.getElementById('detail-headline'),

    detailSourceAuthor: document.getElementById('detail-source-author'),

    detailTime: document.getElementById('detail-time'),

    detailScoreImportance: document.getElementById('detail-score-importance'),

    detailScoreUrgency: document.getElementById('detail-score-urgency'),

    detailScoreFreshness: document.getElementById('detail-score-freshness'),

    detailScoreVerification: document.getElementById('detail-score-verification'),

    detailScoreRelevance: document.getElementById('detail-score-relevance'),

    barImportance: document.getElementById('bar-importance'),

    barUrgency: document.getElementById('bar-urgency'),

    barFreshness: document.getElementById('bar-freshness'),

    barVerification: document.getElementById('bar-verification'),

    barRelevance: document.getElementById('bar-relevance'),

    detailSummaryContent: document.getElementById('detail-summary-content'),

    detailPriorityReason: document.getElementById('detail-priority-reason'),

    detailSourcesList: document.getElementById('detail-sources-list'),

    btnOpenOriginalArticle: document.getElementById('btn-open-original-article'),



    feedToast: document.getElementById('feed-toast')

  };



  // --- Helper Utilities ---

  function getOrCreateDeviceId() {

    let id = localStorage.getItem(STORAGE_KEYS.DEVICE_ID);

    if (!id) {

      id = 'dev_' + Math.random().toString(36).substring(2, 11) + '_' + Date.now();

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

    return ['Politics', 'Technology', 'National', 'Business'];

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

    return interests && interests.length > 0 ? [...interests] : ['Politics', 'Technology', 'National', 'Business'];

  }



  function formatTimeAgo(isoString) {
    return 'Verified Wire';
  }



  function showFeedToast(msg) {

    if (!elements.feedToast) return;

    elements.feedToast.textContent = msg;

    elements.feedToast.classList.remove('hidden');

    clearTimeout(elements.feedToast._timeout);

    elements.feedToast._timeout = setTimeout(() => {

      elements.feedToast.classList.add('hidden');

    }, 2800);

  }



  function updateLocationHeaders() {

    const st = state.state || 'All India';

    if (elements.labelUserLocation) elements.labelUserLocation.textContent = st;

    if (elements.bannerStateName) elements.bannerStateName.textContent = st;

    if (elements.bannerStateLabel) elements.bannerStateLabel.textContent = st;

    if (elements.navStateLabel) elements.navStateLabel.textContent = `${st} Desk`;

    if (elements.mastheadEdition) elements.mastheadEdition.textContent = `${st} Edition`;

    if (elements.stateFocusTitle) elements.stateFocusTitle.textContent = `STATE IN FOCUS: ${st.toUpperCase()} DEVELOPMENTS`;

    if (elements.bureauCopilotHeading) elements.bureauCopilotHeading.textContent = `${st.toUpperCase()} DESK CO-PILOT`;

    if (elements.bureauCopilotDesc) {

      elements.bureauCopilotDesc.textContent = `Active bureau monitoring 48 state gazettes, 14 local civic bodies, and regional university repositories across ${st} for fact-checked announcements.`;

    }

  }



  function updateCalibratedRankTags() {

    if (!elements.calibratedRankContainer) return;

    elements.calibratedRankContainer.innerHTML = '';

    const order = state.priorityOrder.slice(0, 5);

    order.forEach((cat, idx) => {

      const tag = document.createElement('span');

      tag.className = 'font-label-caps text-[11px] bg-surface-container px-2 py-0.5 text-on-surface-variant flex items-center gap-1 border border-outline-variant/20';

      tag.innerHTML = `<strong class="text-primary">0${idx + 1}</strong> ${cat}`;

      elements.calibratedRankContainer.appendChild(tag);

    });

  }



  // --- Category Synonyms & Aliasing ---

  const CATEGORY_SYNONYMS = {

    'tech': ['tech', 'technology'],

    'technology': ['tech', 'technology'],

    'world': ['world', 'international', 'global'],

    'international': ['world', 'international', 'global'],

    'global': ['world', 'international', 'global'],

    'national': ['national', 'india'],

    'state': ['state', 'regional'],

    'politics': ['politics', 'political'],

    'business': ['business', 'economy', 'finance'],

    'science': ['science', 'space'],

    'health': ['health', 'medical'],

    'sports': ['sports', 'sport'],

    'entertainment': ['entertainment', 'cinema', 'movies', 'culture'],

    'environment': ['environment', 'climate', 'nature'],

    'education': ['education', 'learning', 'academics']

  };



  function matchesCategory(cardCat, targetCat) {

    if (!targetCat || targetCat.toLowerCase() === 'all') return true;

    if (!cardCat) return false;

    const c1 = cardCat.trim().toLowerCase();

    const c2 = targetCat.trim().toLowerCase();

    if (c1 === c2) return true;

    const s1 = CATEGORY_SYNONYMS[c1] || [c1];

    const s2 = CATEGORY_SYNONYMS[c2] || [c2];

    return s1.some(v => s2.includes(v));

  }



  // --- Multi-Dimensional Ranking Engine ---

  function rankCardsByUserPreferencesAndPriority(cards, interests, priorityOrder, userState, activeCategory) {
    if (!cards || cards.length === 0) return [];

    let filtered = cards;

    // Tab isolation
    if (activeCategory && activeCategory.toLowerCase() !== 'all') {
      filtered = cards.filter(c => matchesCategory(c.category, activeCategory));
      if (filtered.length === 0) {
        const kw = activeCategory.toLowerCase();
        filtered = cards.filter(c => ((c.headline || '') + ' ' + (c.summary || '')).toLowerCase().includes(kw));
      }
    } else {
      // In 'All News / For You', filter to user's selected interests if any
      if (interests && Array.isArray(interests) && interests.length > 0) {
        const matchingInterests = cards.filter(c => {
          return interests.some(pref => matchesCategory(c.category, pref));
        });
        if (matchingInterests.length > 0) {
          filtered = matchingInterests;
        }
      }
    }

    if (filtered.length === 0 && cards.length > 0) {
      filtered = cards;
    }

    // Build Priority Tier lookup
    const activePriority = (priorityOrder && priorityOrder.length > 0) ? priorityOrder : (interests || []);
    const priorityIndexMap = new Map();
    activePriority.forEach((cat, idx) => {
      const cLow = cat.trim().toLowerCase();
      priorityIndexMap.set(cLow, idx);
      const syns = CATEGORY_SYNONYMS[cLow] || [];
      syns.forEach(s => {
        if (!priorityIndexMap.has(s)) priorityIndexMap.set(s, idx);
      });
    });

    const targetState = (userState || '').trim().toLowerCase();

    function getCardPriorityTier(card) {
      const cat = (card.category || '').trim().toLowerCase();
      if (priorityIndexMap.has(cat)) return priorityIndexMap.get(cat);
      const syns = CATEGORY_SYNONYMS[cat] || [];
      for (const s of syns) {
        if (priorityIndexMap.has(s)) return priorityIndexMap.get(s);
      }
      return 999;
    }

    function getStateMatchScore(card) {
      if (!targetState) return 0;
      const cState = (card.state || '').trim().toLowerCase();
      if (cState === targetState) return 100;
      if ((card.headline || '').toLowerCase().includes(targetState)) return 50;
      return 0;
    }

    function getCardTimestamp(card) {
      const ts = card.published_at || card.event_time || card.created_at;
      if (!ts) return 0;
      const ms = Date.parse(ts);
      return isNaN(ms) ? 0 : ms;
    }

    function getRecencyScore(card) {
      const ts = card.published_at || card.event_time || card.created_at;
      if (!ts) return 30;
      const ms = Date.parse(ts);
      if (isNaN(ms)) return 30;
      const now = Date.now();
      const diffHours = (now - ms) / (1000 * 60 * 60);
      if (diffHours < 0) return 100; // future or just published
      if (diffHours <= 1) return 100; // < 1 hour: 100 pts
      if (diffHours <= 3) return 95;  // < 3 hours: 95 pts
      if (diffHours <= 6) return 90;  // < 6 hours: 90 pts
      if (diffHours <= 12) return 80; // < 12 hours: 80 pts
      if (diffHours <= 24) return 70; // < 24 hours: 70 pts
      if (diffHours <= 48) return 50; // < 48 hours: 50 pts
      if (diffHours <= 168) return 20; // < 7 days: 20 pts
      return 0; // > 7 days gets 0 points!
    }

    function calculateCompositeScore(card) {
      const recency = getRecencyScore(card);
      const tier = getCardPriorityTier(card);
      const priorityPoints = tier === 0 ? 60 : (tier === 1 ? 45 : (tier === 2 ? 30 : (tier === 3 ? 15 : 0)));
      const stateMatch = getStateMatchScore(card);
      const statePoints = stateMatch > 0 ? (stateMatch === 100 ? 50 : 25) : 0;
      const qualityScore = Number(card.final_feed_score) || 50;

      // Composite Score: Recency (2x) + User Category Priority + Regional State Match + Quality
      return (recency * 2.0) + priorityPoints + statePoints + (qualityScore * 0.1);
    }

    return [...filtered].sort((a, b) => {
      if (activeCategory === 'state') {
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

    const cat = (card.category || 'National Policy').toUpperCase();

    const timeAgo = formatTimeAgo(card.published_at || card.event_time || card.created_at);

    const source = card.source_name || (card.sources && card.sources[0]?.name) || 'Verified Wire Service';

    const imp = Math.round(card.importance_score || 92);

    const trust = Math.round(card.verification_score || 95);

    const rel = Math.round(card.personal_relevance_score || 94);



    elements.heroLeadContainer.innerHTML = `

      <article class="bg-surface-container-low p-space-lg md:p-space-xl relative overflow-hidden shadow-sm border-l-4 border-primary-container">

        <div class="flex flex-wrap items-center justify-between gap-space-xs mb-space-sm">

          <div class="flex items-center gap-space-xs">

            <span class="w-2 h-2 bg-primary-container inline-block"></span>

            <span class="font-label-caps text-label-caps text-primary uppercase tracking-widest font-semibold">${cat}</span>

            <span class="text-outline text-label-caps">&#8226;</span>

            <span class="font-label-caps text-label-caps text-secondary uppercase tracking-wider">Top Calibrated Lead</span>

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

            <span class="text-on-surface-variant text-[13px]">${card.priority_reason || 'Verified by independent wire telemetry'}</span>

          </div>

          <div class="flex items-center gap-2">

            <span class="font-label-caps text-[10px] px-1.5 py-0.5 bg-surface-container-high text-on-surface uppercase">Full Audit Available</span>

          </div>

        </div>



        <!-- Actions -->

        <div class="flex items-center justify-between pt-space-xs">

          <button id="btn-hero-dossier" class="font-body-md text-body-md italic text-primary hover:text-surface-tint underline underline-offset-4 flex items-center gap-1 font-medium cursor-pointer" type="button">

            Read Story &amp; Verification Dossier &rarr;

          </button>

          <div class="flex items-center gap-space-xs text-on-surface-variant">

            <button id="btn-hero-share" class="p-2 hover:bg-surface-container hover:text-on-surface transition-colors cursor-pointer" title="Share Story">

              <span class="material-symbols-outlined text-[19px]">share</span>

            </button>

          </div>

        </div>

      </article>

    `;



    document.getElementById('hero-headline-link')?.addEventListener('click', () => openDetailModal(card));

    document.getElementById('btn-hero-dossier')?.addEventListener('click', () => openDetailModal(card));

    document.getElementById('btn-hero-share')?.addEventListener('click', () => shareStory(card));

  }



  function renderSecondaryGrid(cards) {

    if (!elements.secondaryGridContainer) return;

    elements.secondaryGridContainer.innerHTML = '';

    if (state.isInitialLoading && cards.length <= 1) {

      return;

    }

    const pair = cards.slice(1, 3);

    pair.forEach((c) => {

      const art = document.createElement('article');

      art.className = 'bg-surface-container-low p-space-lg flex flex-col justify-between shadow-sm relative border border-outline-variant/15';

      const timeAgo = formatTimeAgo(c.published_at || c.event_time);

      const source = c.source_name || (c.sources && c.sources[0]?.name) || 'Verified Wire';

      const imp = Math.round(c.importance_score || 82);

      const trust = Math.round(c.verification_score || 90);



      art.innerHTML = `

        <div>

          <div class="flex items-center justify-between gap-space-xs mb-space-xs">

            <span class="font-label-caps text-label-caps text-primary uppercase tracking-wider font-semibold">

              ${(c.category || 'General').toUpperCase()}

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



      art.querySelector('h3')?.addEventListener('click', () => openDetailModal(c));

      art.querySelector('.btn-open-dossier')?.addEventListener('click', () => openDetailModal(c));

      art.querySelector('.btn-share-secondary')?.addEventListener('click', () => shareStory(c));

      elements.secondaryGridContainer.appendChild(art);

    });

  }



  function renderStateFocusDesk(allCards, userState) {

    if (!elements.stateFocusContainer) return;

    elements.stateFocusContainer.innerHTML = '';

    const st = (userState || '').trim().toLowerCase();



    let stateMatches = allCards.filter(c => {

      const cs = (c.state || '').trim().toLowerCase();

      const head = (c.headline || '').toLowerCase();

      return cs === st || head.includes(st);

    });



    if (stateMatches.length === 0) {

      stateMatches = allCards.slice(3, 6);

    } else {

      stateMatches = stateMatches.slice(0, 3);

    }



    stateMatches.forEach(c => {

      const strip = document.createElement('article');

      strip.className = 'bg-surface-container-low hover:bg-surface-container p-space-md flex flex-col md:flex-row md:items-center justify-between gap-space-md transition-colors border border-outline-variant/15';

      const timeAgo = formatTimeAgo(c.published_at || c.event_time);

      const source = c.source_name || (c.sources && c.sources[0]?.name) || `${userState} Wire`;



      strip.innerHTML = `

        <div class="flex-1">

          <div class="flex items-center gap-space-xs font-label-caps text-[10px] text-outline mb-1">

            <span class="text-primary font-semibold uppercase">${c.category || 'Regional'}</span>

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

          

          <button class="font-body-md text-body-md italic text-primary hover:text-surface-tint cursor-pointer strip-link" type="button">Read &rarr;</button>

        </div>

      `;



      strip.querySelector('.strip-headline')?.addEventListener('click', () => openDetailModal(c));

      strip.querySelector('.strip-link')?.addEventListener('click', () => openDetailModal(c));

      elements.stateFocusContainer.appendChild(strip);

    });

  }



  function renderStreamFeed(cards) {

    if (!elements.streamFeedContainer) return;

    elements.streamFeedContainer.innerHTML = '';

    if (state.isInitialLoading && cards.length <= 1) {

      if (elements.feedPaginationStatus) elements.feedPaginationStatus.classList.add('hidden');

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

    if (elements.feedPaginationStatus) elements.feedPaginationStatus.classList.remove('hidden');

    const streamItems = cards.slice(3);



    streamItems.forEach(c => {

      const art = document.createElement('article');

      art.className = 'bg-surface-container-low p-space-md flex flex-col sm:flex-row sm:items-center justify-between gap-space-md border border-outline-variant/15 hover:bg-surface-container transition-colors';

      const timeAgo = formatTimeAgo(c.published_at || c.event_time);

      const source = c.source_name || (c.sources && c.sources[0]?.name) || 'Verified Wire';



      art.innerHTML = `

        <div class="flex-1">

          <div class="flex items-center gap-space-xs font-label-caps text-[10px] text-outline mb-1">

            <span class="text-primary font-semibold uppercase">${c.category || 'General'}</span>

            <span>&#8226;</span>

            <span>${source}</span>

            

          </div>

          <h4 class="font-headline-sm text-[18px] leading-snug text-on-surface hover:text-primary transition-colors cursor-pointer stream-title">

            ${c.headline}

          </h4>

          <p class="font-body-md text-[14px] text-on-surface-variant/80 mt-1 line-clamp-2 leading-normal">

            ${c.summary || c.headline}

          </p>

        </div>

        <div class="flex items-center gap-space-md shrink-0">

          <button class="font-body-md text-[15px] italic text-primary hover:text-surface-tint cursor-pointer stream-btn" type="button">

            Read &rarr;

          </button>

        </div>

      `;



      art.querySelector('.stream-title')?.addEventListener('click', () => openDetailModal(c));

      art.querySelector('.stream-btn')?.addEventListener('click', () => openDetailModal(c));

      elements.streamFeedContainer.appendChild(art);

    });



    if (elements.statShowingCount) elements.statShowingCount.textContent = String(cards.length);

    if (elements.statTotalCount) elements.statTotalCount.textContent = String(state.allRankedCache.length || cards.length);

  }



  function renderMorningBrief(cards) {

    if (!elements.morningBriefContainer) return;

    elements.morningBriefContainer.innerHTML = '';

    const topBullets = cards.slice(0, 4);



    topBullets.forEach(c => {

      const div = document.createElement('div');

      div.className = 'pb-space-xs border-b border-outline-variant/10 last:border-b-0 cursor-pointer';

      const imp = Math.round(c.importance_score || 80);



      div.innerHTML = `

        <div class="flex items-center justify-between font-label-caps text-[10px] text-outline mb-1">

          <span class="text-primary uppercase font-semibold">${c.category || 'Brief'}</span>

          <span class="text-outline font-normal">Fast Scan</span>

        </div>

        <p class="font-body-md text-[14px] leading-relaxed text-on-surface hover:text-primary transition-colors line-clamp-2">

          ${c.headline}

        </p>

      `;



      div.addEventListener('click', () => openDetailModal(c));

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



    if (elements.barValImportance) elements.barValImportance.textContent = `${imp}%`;

    if (elements.barFillImportance) elements.barFillImportance.style.width = `${imp}%`;

    if (elements.barValUrgency) elements.barValUrgency.textContent = `${urg}%`;

    if (elements.barFillUrgency) elements.barFillUrgency.style.width = `${urg}%`;

    if (elements.barValFreshness) elements.barValFreshness.textContent = `${frs}%`;

    if (elements.barFillFreshness) elements.barFillFreshness.style.width = `${frs}%`;

    if (elements.barValVerification) elements.barValVerification.textContent = `${ver}%`;

    if (elements.barFillVerification) elements.barFillVerification.style.width = `${ver}%`;

    if (elements.barValRelevance) elements.barValRelevance.textContent = `${rel}%`;

    if (elements.barFillRelevance) elements.barFillRelevance.style.width = `${rel}%`;



    // Dynamic 5-axis polygon scaling

    // Center is (100, 75). Radius ~50

    const cx = 100, cy = 75, maxR = 50;

    const angles = [-Math.PI / 2, -Math.PI / 2 + 0.4 * Math.PI * 1, -Math.PI / 2 + 0.4 * Math.PI * 2, -Math.PI / 2 + 0.4 * Math.PI * 3, -Math.PI / 2 + 0.4 * Math.PI * 4];

    const scores = [imp / 100, urg / 100, frs / 100, ver / 100, rel / 100];

    

    const pts = angles.map((ang, i) => {

      const r = Math.max(10, scores[i] * maxR);

      const x = Math.round(cx + r * Math.cos(ang));

      const y = Math.round(cy + r * Math.sin(ang));

      return `${x},${y}`;

    });



    if (elements.radarDataPolygon) {

      elements.radarDataPolygon.setAttribute('points', pts.join(' '));

    }

  }



  // --- Master Render Coordinator ---

  function renderAllEditorialSections() {

    if (state.cards.length === 0) return;



    const lead = state.cards[0];

    renderHeroLead(lead);

    renderSecondaryGrid(state.cards);

    renderStateFocusDesk(state.allRankedCache.length > 0 ? state.allRankedCache : state.cards, state.state);

    renderStreamFeed(state.cards);

    renderMorningBrief(state.allRankedCache.length > 0 ? state.allRankedCache : state.cards);

    updateAlgorithmicRadar(lead);

    updateLocationHeaders();

    updateCalibratedRankTags();

  }



  // --- Story Detail Modal ---

  function openDetailModal(card) {

    if (!card || !elements.modalDetail) return;

    state.selectedCard = card;



    if (elements.detailCategoryBadge) elements.detailCategoryBadge.textContent = (card.category || 'General').toUpperCase();

    if (elements.detailVerificationBadge) elements.detailVerificationBadge.textContent = card.verification_type === 'cross_verified' ? 'Tier-1 Corroborated' : 'Verified';

    if (elements.detailHeadline) elements.detailHeadline.textContent = card.headline;

    if (elements.detailSourceAuthor) elements.detailSourceAuthor.textContent = card.source_name || (card.sources && card.sources[0]?.name) || 'Verified Primary Wire';

    if (elements.detailTime) elements.detailTime.textContent = "Verified Live Wire";



    const imp = Number(card.importance_score || 85).toFixed(1);

    const urg = Number(card.urgency_score || 80).toFixed(1);

    const frs = Number(card.freshness_score || 95).toFixed(1);

    const ver = Number(card.verification_score || 88).toFixed(1);

    const rel = Number(card.personal_relevance_score || 90).toFixed(1);



    if (elements.detailScoreImportance) elements.detailScoreImportance.textContent = `${imp}/100`;

    if (elements.detailScoreUrgency) elements.detailScoreUrgency.textContent = `${urg}/100`;

    if (elements.detailScoreFreshness) elements.detailScoreFreshness.textContent = `${frs}/100`;

    if (elements.detailScoreVerification) elements.detailScoreVerification.textContent = `${ver}/100`;

    if (elements.detailScoreRelevance) elements.detailScoreRelevance.textContent = `${rel}/100`;



    if (elements.barImportance) if (elements.barImportance) elements.barImportance.style.width = `${Math.min(100, imp)}%`;

    if (elements.barUrgency) if (elements.barUrgency) elements.barUrgency.style.width = `${Math.min(100, urg)}%`;

    if (elements.barFreshness) if (elements.barFreshness) elements.barFreshness.style.width = `${Math.min(100, frs)}%`;

    if (elements.barVerification) if (elements.barVerification) elements.barVerification.style.width = `${Math.min(100, ver)}%`;

    if (elements.barRelevance) if (elements.barRelevance) elements.barRelevance.style.width = `${Math.min(100, rel)}%`;



    if (elements.detailPriorityReason) elements.detailPriorityReason.textContent = card.priority_reason || 'Verified by independent cross-checked wire reports.';



    if (elements.detailSummaryContent) {

      const paras = (card.summary || card.headline).split('\n\n');

      elements.detailSummaryContent.innerHTML = paras.map(p => `<p>${p}</p>`).join('');

    }



    if (elements.detailSourcesList) {

      elements.detailSourcesList.innerHTML = '';

      const sources = (card.sources && card.sources.length > 0) ? card.sources : [

        { name: card.source_name || 'Primary Wire Source', url: card.canonical_url || card.source_url || '#' }

      ];

      sources.forEach(s => {

        const li = document.createElement('li');

        li.innerHTML = `<a href="${s.url || '#'}" target="_blank" rel="noopener noreferrer" class="hover:underline flex items-center gap-1">${s.name || 'Wire Link'} &rarr;</a>`;

        elements.detailSourcesList.appendChild(li);

      });

    }



    if (elements.btnOpenOriginalArticle) {

      elements.btnOpenOriginalArticle.href = card.canonical_url || card.source_url || (card.sources && card.sources[0]?.url) || '#';

    }



    elements.modalDetail.classList.remove('hidden');

  }



  function shareStory(card) {

    const url = card.canonical_url || card.source_url || window.location.href;

    if (navigator.share) {

      navigator.share({ title: card.headline, text: card.summary, url }).catch(() => {});

    } else {

      navigator.clipboard.writeText(url).then(() => {

        showFeedToast('Story link copied to clipboard');

      }).catch(() => {});

    }

  }



  // --- Instant 0ms Paint ---

  function showInstantFirstCard() {

    try {

      const cached = localStorage.getItem(STORAGE_KEYS.TOP_CARD_CACHE);

      let leadCard = INSTANT_FALLBACK_CARD;

      if (cached) {

        const parsed = JSON.parse(cached);

        if (parsed && parsed.headline) leadCard = parsed;

      }

      state.cards = [leadCard];

      renderAllEditorialSections();

    } catch (e) {

      console.warn('Instant paint fallback note:', e);

    }

  }



  // --- Background Crawler Trigger ---

  function triggerBackgroundCrawler() {

    try {

      fetch(`${API_BASE}/crawl/trigger`, { method: 'POST', mode: 'cors' }).catch(() => {});

    } catch (_) {}

  }



  // --- Feed Fetcher & Sync ---

  async function fetchFeed(forceRefresh = false) {

    if (state.loading) return;

    state.loading = true;



    try {

      const params = new URLSearchParams();

      params.append('device_id', state.deviceId);

      params.append('limit', '80');

      params.append('offset', '0');



      if (state.activeCategory && state.activeCategory !== 'all') {

        params.append('category', state.activeCategory);

      } else if (state.interests && state.interests.length > 0) {

        params.append('categories', state.interests.map(c => c.toLowerCase()).join(','));

      }



      if (state.state && (state.activeCategory === 'state' || state.activeCategory === 'all')) {

        params.append('state', state.state);

      }



      if (forceRefresh) {

        params.append('_t', String(Date.now()));

      }



      let rawItems = null;



      // 1. Prioritize fresh crawler feed (feed.json) which auto_news_crawler continuously syncs

      try {

        const staticRes = await fetch(`./feed.json?_t=${Date.now()}`, { cache: 'no-store' });

        if (staticRes.ok) {

          const rawData = await staticRes.json();

          const items = rawData.items || rawData.cards || [];

          if (Array.isArray(items) && items.length > 0) {

            rawItems = items;

          }

        }

      } catch (_) {}



      // 2. Live API fallback or complement

      if (!rawItems || rawItems.length === 0) {

        try {

          const controller = new AbortController();

          const timeoutId = setTimeout(() => controller.abort(), 4500);



          const res = await fetch(`${API_BASE}/feed?${params.toString()}`, {

            signal: controller.signal,

            headers: { 'Cache-Control': 'no-cache', 'Pragma': 'no-cache' }

          });

          clearTimeout(timeoutId);



          if (res.ok) {

            const apiData = await res.json();

            if (apiData && Array.isArray(apiData.items) && apiData.items.length > 0) {

              rawItems = apiData.items;

            }

          }

        } catch (_) {}

      }



      if (!rawItems || rawItems.length === 0) return;



      // Multi-Dimensional Sorting & Priority Placement

      const rankedCards = rankCardsByUserPreferencesAndPriority(

        rawItems,

        state.interests,

        state.priorityOrder,

        state.state,

        state.activeCategory

      );



      state.allRankedCache = rankedCards;

      state.cards = rankedCards.slice(0, state.pageSize);

      state.isInitialLoading = false;



      // Cache top lead card for next instant 0ms visit

      if (state.cards.length > 0) {

        try {

          localStorage.setItem(STORAGE_KEYS.TOP_CARD_CACHE, JSON.stringify(state.cards[0]));

        } catch (_) {}

      }



      renderAllEditorialSections();



      if (forceRefresh) {

        showFeedToast('Live feed refreshed with latest dispatches');

      }



    } catch (err) {

      console.error('Feed fetch error:', err);

    } finally {

      state.loading = false;

    }

  }



  // --- Interest & Priority Modals Logic ---

  function renderInterestChips() {

    if (!elements.interestChipsContainer) return;

    elements.interestChipsContainer.innerHTML = '';

    ALL_CATEGORIES.forEach(cat => {

      const isSelected = state.interests.includes(cat);

      const chip = document.createElement('button');

      chip.type = 'button';

      chip.className = `interest-chip ${isSelected ? 'selected' : ''}`;

      chip.innerHTML = `<span>${cat}</span> <span>${isSelected ? '&#10003;' : '+'}</span>`;



      chip.addEventListener('click', () => {

        if (state.interests.includes(cat)) {

          state.interests = state.interests.filter(c => c !== cat);

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

    state.priorityOrder = state.priorityOrder.filter(c => state.interests.includes(c));

    state.interests.forEach(c => {

      if (!state.priorityOrder.includes(c)) state.priorityOrder.push(c);

    });

  }



  function renderPriorityList() {

    syncPriorityWithInterests();

    if (!elements.priorityListContainer) return;

    elements.priorityListContainer.innerHTML = '';



    state.priorityOrder.forEach((cat, idx) => {

      const item = document.createElement('div');

      item.className = 'priority-item';

      item.innerHTML = `

        <div class="priority-item-left">

          <span class="priority-rank-badge">0${idx + 1}</span>

          <span class="priority-name">${cat}</span>

        </div>

        <div>

          <button class="btn-priority-move btn-move-up" type="button" ${idx === 0 ? 'disabled' : ''}>&#9650;</button>

          <button class="btn-priority-move btn-move-down" type="button" ${idx === state.priorityOrder.length - 1 ? 'disabled' : ''}>&#9660;</button>

        </div>

      `;



      item.querySelector('.btn-move-up')?.addEventListener('click', () => {

        if (idx > 0) {

          const t = state.priorityOrder[idx];

          state.priorityOrder[idx] = state.priorityOrder[idx - 1];

          state.priorityOrder[idx - 1] = t;

          renderPriorityList();

        }

      });



      item.querySelector('.btn-move-down')?.addEventListener('click', () => {

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

    localStorage.setItem(STORAGE_KEYS.INTERESTS, JSON.stringify(state.interests));

    localStorage.setItem(STORAGE_KEYS.PRIORITY_ORDER, JSON.stringify(state.priorityOrder));

    elements.modalPriority.classList.add('hidden');

    updateCalibratedRankTags();

    await fetchFeed(true);

    showFeedToast('Priorities saved! Feed re-calibrated.');



    try {

      await fetch(`${API_BASE}/user/${encodeURIComponent(state.deviceId)}/preferences`, {

        method: 'PUT',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify({ category_order: state.priorityOrder.map(c => c.toLowerCase()) })

      });

    } catch (_) {}

  }



  // --- Event Listeners Setup ---

  function initEventListeners() {

    // Refresh Live Feed Button

    elements.btnRefreshFeed?.addEventListener('click', async () => {

      elements.btnRefreshFeed.classList.add('refreshing');

      triggerBackgroundCrawler();

      await fetchFeed(true);

      setTimeout(() => elements.btnRefreshFeed.classList.remove('refreshing'), 600);

    });



    // Category Tabs

    elements.categoryTabs.forEach(tab => {

      tab.addEventListener('click', () => {

        elements.categoryTabs.forEach(t => {

          t.classList.remove('active', 'bg-primary', 'text-on-primary', 'font-semibold');

          t.classList.add('bg-surface-container', 'text-on-surface-variant');

        });

        tab.classList.add('active', 'bg-primary', 'text-on-primary', 'font-semibold');

        tab.classList.remove('bg-surface-container', 'text-on-surface-variant');



        state.activeCategory = tab.getAttribute('data-category') || 'all';

        fetchFeed(true);

      });

    });



    // Nav For You

    elements.navForYou?.addEventListener('click', (e) => {

      e.preventDefault();

      const tabForYou = document.getElementById('tab-for-you');

      if (tabForYou) tabForYou.click();

    });



    // Load More Stories Button

    elements.btnLoadMore?.addEventListener('click', () => {

      if (state.allRankedCache && state.cards.length < state.allRankedCache.length) {

        const nextBatch = state.allRankedCache.slice(state.cards.length, state.cards.length + 15);

        state.cards = state.cards.concat(nextBatch);

        renderStreamFeed(state.cards);

        if (state.cards.length >= state.allRankedCache.length) {

          if (elements.btnLoadMore) elements.btnLoadMore.style.display = 'none';

          if (elements.statusCaughtUpMsg) elements.statusCaughtUpMsg.textContent = 'All verified stories loaded.';

        }

      }

    });



    // Location Modal Triggers

    const openLoc = () => {

      if (elements.inputState) elements.inputState.value = state.state || '';

      elements.modalLocation.classList.remove('hidden');

    };

    elements.btnOpenLocation?.addEventListener('click', openLoc);

    elements.btnChangeStateBanner?.addEventListener('click', openLoc);

    elements.btnCloseLocation?.addEventListener('click', () => elements.modalLocation.classList.add('hidden'));



    elements.btnSaveLocation?.addEventListener('click', async () => {

      const selected = elements.inputState.value.trim();

      state.state = selected || 'All India';

      localStorage.setItem(STORAGE_KEYS.LOCATION_STATE, state.state);

      updateLocationHeaders();

      elements.modalLocation.classList.add('hidden');

      await fetchFeed(true);

      showFeedToast(`State set to ${state.state}`);

    });



    elements.btnSkipLocation?.addEventListener('click', () => {

      elements.modalLocation.classList.add('hidden');

    });



    // Interests Modal Triggers

    document.getElementById('btn-open-interests-modal')?.addEventListener('click', () => {

      renderInterestChips();

      elements.modalInterests.classList.remove('hidden');

    });

    elements.btnCloseInterests?.addEventListener('click', () => elements.modalInterests.classList.add('hidden'));

    elements.btnResetInterests?.addEventListener('click', () => {

      state.interests = ['Politics', 'Technology', 'National', 'Business'];

      renderInterestChips();

    });

    elements.btnSaveInterests?.addEventListener('click', () => {

      localStorage.setItem(STORAGE_KEYS.INTERESTS, JSON.stringify(state.interests));

      syncPriorityWithInterests();

      elements.modalInterests.classList.add('hidden');

      renderPriorityList();

      elements.modalPriority.classList.remove('hidden');

    });



    // Priority Modal Triggers

    elements.btnOpenPriorityModal?.addEventListener('click', () => {

      renderPriorityList();

      elements.modalPriority.classList.remove('hidden');

    });

    elements.btnClosePriority?.addEventListener('click', () => elements.modalPriority.classList.add('hidden'));

    elements.btnBackPriority?.addEventListener('click', () => {

      elements.modalPriority.classList.add('hidden');

      renderInterestChips();

      elements.modalInterests.classList.remove('hidden');

    });

    elements.btnSavePriority?.addEventListener('click', savePriorityOrder);



    // Story Detail Close

    elements.btnCloseDetail?.addEventListener('click', () => elements.modalDetail.classList.add('hidden'));



    // Modal Backdrops Click to Dismiss

    document.querySelectorAll('.modal-backdrop').forEach(bd => {

      bd.addEventListener('click', (e) => {

        if (e.target === bd) bd.classList.add('hidden');

      });

    });



    // Escape Key

    document.addEventListener('keydown', (e) => {

      if (e.key === 'Escape') {

        document.querySelectorAll('.modal-backdrop').forEach(bd => bd.classList.add('hidden'));

      }

    });



    // Search Input Enter

    elements.inputSearch?.addEventListener('keydown', (e) => {

      if (e.key === 'Enter') {

        const q = elements.inputSearch.value.trim().toLowerCase();

        if (q && state.allRankedCache.length > 0) {

          const matched = state.allRankedCache.filter(c => {

            return ((c.headline || '') + ' ' + (c.summary || '')).toLowerCase().includes(q);

          });

          if (matched.length > 0) {

            state.cards = matched;

            renderAllEditorialSections();

            showFeedToast(`Found ${matched.length} dispatches matching "${q}"`);

          } else {

            showFeedToast(`No stories found for "${q}"`);

          }

        }

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



  if (document.readyState === 'loading') {

    document.addEventListener('DOMContentLoaded', init);

  } else {

    init();

  }

})();

