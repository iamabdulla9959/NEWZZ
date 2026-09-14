/**
 * News Reels — Modern Multi-Dimensional Web App
 * Connects to the FastAPI backend and renders structured, explainable news cards.
 */

(function () {
  'use strict';

  // --- Constants & Config ---
  // Smart API Base resolution for Localhost, Netlify proxy (/api), and custom Render backend
  let API_BASE = window.RENDER_API_BASE || '';
  if (!API_BASE) {
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
      API_BASE = window.location.origin;
    } else if (window.location.hostname.includes('netlify.app')) {
      // Connect directly to live Render backend
      API_BASE = 'https://newzz-5e19.onrender.com';
    } else if (window.location.hostname.includes('github.io')) {
      API_BASE = 'https://newzz-5e19.onrender.com';
    } else {
      API_BASE = window.location.origin;
    }
  }
  const STORAGE_KEYS = {
    DEVICE_ID: 'newsreels_device_id',
    LOCATION_STATE: 'newsreels_state',
    INTERESTS: 'newsreels_interests',
    PRIORITY_ORDER: 'newsreels_priority_order',
    ONBOARDING_COMPLETE: 'newsreels_onboarding_complete'
  };

  const ALL_CATEGORIES = [
    'Technology', 'Politics', 'Business', 'National', 'World',
    'Science', 'Health', 'Sports', 'Entertainment', 'Environment'
  ];

  // --- State ---
  let state = {
    deviceId: getOrCreateDeviceId(),
    state: localStorage.getItem(STORAGE_KEYS.LOCATION_STATE) || '',
    activeCategory: 'all',
    interests: getStoredInterests(),
    priorityOrder: getStoredPriorityOrder(),
    cards: [],
    cardIds: new Set(),       // Track rendered card IDs to prevent duplicates
    selectedCard: null,
    loading: false,
    offset: 0,                // Current pagination offset
    hasMore: true,            // Whether more pages are available
    pageSize: 30,             // Cards per page
  };

  // --- DOM Elements ---
  const elements = {
    feedContainer: document.getElementById('feed-container'),
    categoryTabs: document.querySelectorAll('.category-tab'),
    loadingState: document.getElementById('loading-state-view'),
    emptyState: document.getElementById('empty-state-view'),
    btnEmptyReset: document.getElementById('btn-empty-reset'),
    btnRefresh: document.getElementById('btn-refresh-feed'),
    
    // Header labels
    labelLocation: document.getElementById('label-user-location'),
    labelInterests: document.getElementById('label-user-interests'),
    
    // Welcome Modal
    modalWelcome: document.getElementById('modal-welcome'),
    btnWelcomeStart: document.getElementById('btn-welcome-start'),

    // Location Modal
    modalLocation: document.getElementById('modal-location'),
    btnOpenLocation: document.getElementById('btn-open-location-modal'),
    btnCloseLocation: document.getElementById('btn-close-location-modal'),
    inputState: document.getElementById('input-state'),
    btnSaveLocation: document.getElementById('btn-save-location'),
    btnSkipLocation: document.getElementById('btn-skip-location'),

    // Interests Modal
    modalInterests: document.getElementById('modal-interests'),
    btnOpenInterests: document.getElementById('btn-open-interests-modal'),
    btnCloseInterests: document.getElementById('btn-close-interests-modal'),
    interestChipsContainer: document.getElementById('interest-chips-container'),
    btnSaveInterests: document.getElementById('btn-save-interests'),
    btnResetInterests: document.getElementById('btn-reset-interests'),

    // Priority Modal
    modalPriority: document.getElementById('modal-priority'),
    btnClosePriority: document.getElementById('btn-close-priority-modal'),
    btnBackPriority: document.getElementById('btn-back-priority'),
    btnSavePriority: document.getElementById('btn-save-priority'),
    priorityListContainer: document.getElementById('priority-list-container'),
    priorityErrorBanner: document.getElementById('priority-error-banner'),
    priorityErrorMsg: document.getElementById('priority-error-msg'),

    // Story Detail Modal
    modalDetail: document.getElementById('modal-story-detail'),
    btnCloseDetail: document.getElementById('btn-close-detail-modal'),
    detailCategoryBadge: document.getElementById('detail-category-badge'),
    detailVerificationBadge: document.getElementById('detail-verification-badge'),
    detailHeadline: document.getElementById('detail-headline'),
    detailSourceAuthor: document.getElementById('detail-source-author'),
    detailTime: document.getElementById('detail-time'),
    detailFinalScore: document.getElementById('detail-final-score'),
    detailPriorityReason: document.getElementById('detail-priority-reason'),
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
    detailSourcesList: document.getElementById('detail-sources-list'),
    btnOpenOriginalArticle: document.getElementById('btn-open-original-article')
  };

  // --- Helper Functions ---
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
        return JSON.parse(stored);
      }
    } catch (e) {
      console.warn('Error reading stored interests', e);
    }
    return ['Technology', 'National', 'Business', 'Politics'];
  }

  function getStoredPriorityOrder() {
    try {
      const stored = localStorage.getItem(STORAGE_KEYS.PRIORITY_ORDER);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed)) {
          return parsed;
        }
      }
    } catch (e) {
      console.warn('Error reading stored priority order', e);
    }
    return null;
  }

  function updateLocationBadge() {
    if (state.state) {
      elements.labelLocation.textContent = state.state;
      elements.labelLocation.parentElement.classList.add('active-location');
    } else {
      elements.labelLocation.textContent = 'Set Location';
      elements.labelLocation.parentElement.classList.remove('active-location');
    }
  }

  function formatTimeAgo(isoString) {
    if (!isoString) return 'Recent';
    try {
      const date = new Date(isoString);
      const diffSec = Math.floor((Date.now() - date.getTime()) / 1000);
      if (diffSec < 60) return 'Just now';
      if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
      if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
      return `${Math.floor(diffSec / 86400)}d ago`;
    } catch {
      return 'Recent';
    }
  }

  function getScoreBadgeClass(score) {
    if (score >= 80) return 'score-high';
    if (score >= 50) return 'score-med';
    return 'score-low';
  }

  function getTrustBadgeInfo(card) {
    const vScore = card.verification_score != null ? card.verification_score : 70;
    const vStatus = card.verification_status || '';
    
    if (vScore >= 90 || vStatus === 'corroborated' || vStatus === 'verified') {
      return { text: 'Tier-1 Corroborated', class: 'trust-high' };
    }
    if (vScore >= 75) {
      return { text: 'Reputable Source', class: 'trust-med' };
    }
    if (vScore < 60) {
      return { text: 'Developing / Single Source', class: 'trust-low' };
    }
    return { text: 'Verified', class: 'trust-med' };
  }

  // --- API Communication ---
  let _scrollObserver = null;  // IntersectionObserver for infinite scroll sentinel
  let _activeFetchGeneration = 0; // Generation tracker to prevent race conditions during filter/tab switches

  function _resetPagination() {
    _activeFetchGeneration++;
    state.cards = [];
    state.cardIds = new Set();
    state.offset = 0;
    state.hasMore = true;
    state.loading = false;
    _detachScrollObserver();
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
    'education': ['education']
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

  // --- State Preference News Prioritizer ---
  function rankCardsByStatePreference(cards, userState, activeCategory) {
    if (!cards || cards.length === 0 || !userState) return cards;
    const targetState = userState.trim().toLowerCase();

    return [...cards].sort((a, b) => {
      // 1. Exact state match: card.state strictly matches user's chosen state
      const aState = (a.state || '').trim().toLowerCase();
      const bState = (b.state || '').trim().toLowerCase();
      const aExact = aState === targetState ? 100 : 0;
      const bExact = bState === targetState ? 100 : 0;

      // 2. Headline location mention (explicit regional story)
      const aHead = (a.headline || '').toLowerCase().includes(targetState) ? 50 : 0;
      const bHead = (b.headline || '').toLowerCase().includes(targetState) ? 50 : 0;

      const aScore = aExact || aHead;
      const bScore = bExact || bHead;

      if (aScore !== bScore) {
        return bScore - aScore; // Stories for user's state ALWAYS appear first
      }

      // Maintain feed importance score order
      return (Number(b.final_feed_score) || 0) - (Number(a.final_feed_score) || 0);
    });
  }

  async function fetchFeed(append = false) {
    if (state.loading) return;
    if (!append && !state.hasMore && state.cards.length > 0) return;

    const currentGen = append ? _activeFetchGeneration : ++_activeFetchGeneration;
    state.loading = true;
    if (!append) {
      renderLoading(true);
      elements.emptyState.classList.add('hidden');
    }

    try {
      const params = new URLSearchParams();
      params.append('device_id', state.deviceId);
      params.append('limit', String(state.pageSize));
      params.append('offset', String(state.offset));

      if (state.activeCategory && state.activeCategory !== 'all') {
        params.append('category', state.activeCategory);
      }
      // Only filter strictly by state when on 'state' tab or 'all' news,
      // so specific topic categories (Tech, World, Science, etc.) are never empty
      // if the backend DB lacks local regional articles for that specific topic.
      if (state.state && (state.activeCategory === 'state' || state.activeCategory === 'all')) {
        params.append('state', state.state);
      }

      let data = null;
      try {
        const res = await fetch(`${API_BASE}/feed?${params.toString()}`);
        if (res.ok) {
          data = await res.json();
        }
      } catch (e) {
        // Server unreachable, fall through to static fallback
      }

      // Smart Multi-Layer Fallback Guardrail:
      // If live API is unreachable, times out, OR returns 0 items for this filter,
      // immediately fall back to the bundled rich feed.json (948+ verified articles)!
      const hasLiveItems = data && Array.isArray(data.items) && data.items.length > 0;
      if (!hasLiveItems) {
        try {
          const staticRes = await fetch('./feed.json');
          if (staticRes.ok) {
            const rawData = await staticRes.json();
            let allCards = rawData.items || rawData.cards || [];

            if (state.activeCategory && state.activeCategory !== 'all') {
              const matched = allCards.filter(c => matchesCategory(c.category, state.activeCategory));
              if (matched.length > 0) {
                allCards = matched;
              } else {
                // Keyword match fallback in headline / summary
                const kw = state.activeCategory.toLowerCase();
                const kwMatched = allCards.filter(c => {
                  const text = ((c.headline || '') + ' ' + (c.summary || '')).toLowerCase();
                  return text.includes(kw);
                });
                if (kwMatched.length > 0) {
                  allCards = kwMatched;
                }
              }
            }

            if (state.state && (state.activeCategory === 'state' || state.activeCategory === 'all')) {
              allCards = rankCardsByStatePreference(allCards, state.state, state.activeCategory);
            }

            // Ultimate guardrail: If any filter ever yields 0 cards,
            // fall back to trending cards so the user NEVER gets an empty screen!
            if (allCards.length === 0 && rawData.items && rawData.items.length > 0) {
              allCards = rawData.items;
            }

            const paged = allCards.slice(state.offset, state.offset + state.pageSize);
            data = {
              items: paged,
              total: allCards.length,
              fallback_used: true
            };
          }
        } catch (staticErr) {
          console.warn('Static demo feed fallback failed:', staticErr);
        }
      }

      if (!data) {
        throw new Error('Feed data unavailable');
      }

      // If a newer search/tab/filter was initiated while this request was in flight, discard this stale response
      if (currentGen !== _activeFetchGeneration) {
        return;
      }

      let newItems = Array.isArray(data) ? data : (data.items || data.cards || []);
      const total = data.total || newItems.length;

      // Prioritize user's state news first in State and All categories
      if (state.state && (state.activeCategory === 'state' || state.activeCategory === 'all')) {
        newItems = rankCardsByStatePreference(newItems, state.state, state.activeCategory);
      }

      if (append) {
        // Append only non-duplicate cards
        const freshItems = newItems.filter(c => c && c.id && !state.cardIds.has(c.id));
        freshItems.forEach(c => { state.cards.push(c); state.cardIds.add(c.id); });
        if (freshItems.length > 0) {
          appendCards(freshItems);
        }
      } else {
        state.cards = newItems.filter(c => c && c.id);
        state.cardIds = new Set(state.cards.map(c => c.id));
        renderFeed();
      }

      state.offset += newItems.length;
      state.hasMore = state.offset < total && newItems.length >= state.pageSize;

      // Update the scroll total indicator
      const totalEl = document.querySelector('.scroll-total');
      if (totalEl) totalEl.textContent = total > state.cards.length ? `${state.cards.length}+` : String(state.cards.length);

      // Attach or detach scroll observer
      if (state.hasMore) {
        _attachScrollObserver();
      } else {
        _detachScrollObserver();
      }
    } catch (err) {
      if (currentGen !== _activeFetchGeneration) return;
      console.error('Failed to load feed:', err);
      if (!append) {
        state.cards = [];
        renderFeed();
      }
    } finally {
      if (currentGen === _activeFetchGeneration) {
        state.loading = false;
        if (!append) renderLoading(false);
      }
    }
  }

  function _attachScrollObserver() {
    _detachScrollObserver();
    let sentinel = document.getElementById('feed-scroll-sentinel');
    if (!sentinel) {
      sentinel = document.createElement('div');
      sentinel.id = 'feed-scroll-sentinel';
      sentinel.style.cssText = 'height:4px;width:100%;pointer-events:none;';
      elements.feedContainer.appendChild(sentinel);
    }
    _scrollObserver = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && state.hasMore && !state.loading) {
        fetchFeed(true);
      }
    }, { root: elements.feedContainer, threshold: 0.1, rootMargin: '200px' });
    _scrollObserver.observe(sentinel);
  }

  function _detachScrollObserver() {
    if (_scrollObserver) {
      _scrollObserver.disconnect();
      _scrollObserver = null;
    }
  }

  // --- Render Functions ---
  function renderLoading(isLoading) {
    if (isLoading) {
      elements.loadingState.classList.remove('hidden');
      elements.feedContainer.classList.add('opacity-faded');
    } else {
      elements.loadingState.classList.add('hidden');
      elements.feedContainer.classList.remove('opacity-faded');
    }
  }

  function renderFeed() {
    elements.feedContainer.innerHTML = '';
    const count = state.cards.length;

    if (count === 0) {
      elements.emptyState.classList.remove('hidden');
      return;
    }

    elements.emptyState.classList.add('hidden');

    // Add scroll position indicator
    const indicator = document.createElement('div');
    indicator.className = 'scroll-indicator';
    indicator.id = 'scroll-indicator';
    indicator.innerHTML = `<span class="scroll-current">1</span> / <span class="scroll-total">${count}</span>`;
    elements.feedContainer.appendChild(indicator);

    state.cards.forEach((card, index) => {
      const cardEl = createCardElement(card, index, count);
      elements.feedContainer.appendChild(cardEl);
    });

    // Track scroll position
    const cards = elements.feedContainer.querySelectorAll('.scroll-card');
    const currentSpan = indicator.querySelector('.scroll-current');
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const idx = entry.target.getAttribute('data-card-index');
          currentSpan.textContent = Number(idx) + 1;
        }
      });
    }, { root: elements.feedContainer, threshold: 0.6 });

    cards.forEach(c => observer.observe(c));
  }

  // Append additional cards to the existing feed (infinite scroll)
  function appendCards(newCards) {
    if (!newCards || newCards.length === 0) return;
    const totalCount = state.cards.length;
    const startIndex = totalCount - newCards.length;

    // Reuse existing scroll-indicator if present
    let indicator = document.getElementById('scroll-indicator');
    if (!indicator) {
      indicator = document.createElement('div');
      indicator.className = 'scroll-indicator';
      indicator.id = 'scroll-indicator';
      indicator.innerHTML = `<span class="scroll-current">1</span> / <span class="scroll-total">${totalCount}</span>`;
      elements.feedContainer.prepend(indicator);
    }
    const currentSpan = indicator.querySelector('.scroll-current');
    const totalSpan = indicator.querySelector('.scroll-total');
    if (totalSpan) totalSpan.textContent = totalCount;

    // Remove sentinel so we can re-append it after new cards
    const oldSentinel = document.getElementById('feed-scroll-sentinel');
    if (oldSentinel) oldSentinel.remove();

    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const idx = entry.target.getAttribute('data-card-index');
          if (currentSpan) currentSpan.textContent = Number(idx) + 1;
        }
      });
    }, { root: elements.feedContainer, threshold: 0.6 });

    newCards.forEach((card, i) => {
      const globalIndex = startIndex + i;
      const cardEl = createCardElement(card, globalIndex, totalCount);
      elements.feedContainer.appendChild(cardEl);
      observer.observe(cardEl);
    });
  }

  function createCardElement(card, index, totalCount) {
    const cardEl = document.createElement('article');
    cardEl.className = 'scroll-card';
    cardEl.id = `news-card-${card.id || index}`;
    cardEl.setAttribute('data-card-id', card.id);
    cardEl.setAttribute('data-card-index', index);

    const trust = getTrustBadgeInfo(card);
    const timeAgo = formatTimeAgo(card.event_time || card.published_at || card.created_at);
    const summaryText = card.summary || card.headline;
    const firstSource = (card.sources && card.sources.length > 0) ? card.sources[0] : null;
    const sourceName = card.source_name || (firstSource ? firstSource.name : 'Verified Source');
    const sourceUrl = card.canonical_url || card.source_url || (firstSource ? firstSource.url : '#');
    const scoreVal = Number(card.final_feed_score || 0).toFixed(1);

    cardEl.innerHTML = `
      <div class="scroll-card-inner">
        <div class="scroll-card-top">
          <div class="scroll-badges">
            <span class="badge badge-category">${card.category || 'General'}</span>
            <span class="badge ${trust.class}">${trust.text}</span>
          </div>
          <span class="scroll-time">${timeAgo}</span>
        </div>

        <div class="scroll-card-body" id="body-${card.id}">
          <h2 class="scroll-headline">${card.headline}</h2>
          <p class="scroll-summary">${summaryText}</p>
        </div>

        <div class="scroll-card-meta">
          <span class="scroll-source">${sourceName}</span>
        </div>

        <div class="scroll-card-actions">
          <button class="scroll-action-btn" id="btn-share-${card.id}" title="Share this story">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="18" cy="5" r="3"/>
              <circle cx="6" cy="12" r="3"/>
              <circle cx="18" cy="19" r="3"/>
              <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/>
              <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
            </svg>
            Share
          </button>
          <a href="${sourceUrl}" target="_blank" rel="noopener noreferrer" class="scroll-action-btn scroll-action-primary" id="btn-read-${card.id}">
            Read Full Story &rarr;
          </a>
        </div>
      </div>
    `;

    // Share handler
    const btnShare = cardEl.querySelector(`#btn-share-${card.id}`);
    if (btnShare) {
      btnShare.addEventListener('click', () => {
        if (navigator.share) {
          navigator.share({
            title: card.headline,
            text: (card.summary || card.headline).substring(0, 200),
            url: sourceUrl
          }).catch(() => {});
        } else {
          navigator.clipboard.writeText(sourceUrl).then(() => {
            btnShare.textContent = 'Link Copied!';
            setTimeout(() => { btnShare.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg> Share`; }, 1500);
          }).catch(() => {});
        }
      });
    }

    // Tap headline/body to open detail modal with explainability data
    const bodyArea = cardEl.querySelector(`#body-${card.id}`);
    if (bodyArea) {
      bodyArea.style.cursor = 'pointer';
      bodyArea.addEventListener('click', () => openDetailModal(card));
    }

    return cardEl;
  }

  function openDetailModal(card) {
    state.selectedCard = card;
    const trust = getTrustBadgeInfo(card);

    elements.detailCategoryBadge.textContent = card.category || 'General';
    elements.detailVerificationBadge.textContent = trust.text;
    elements.detailVerificationBadge.className = `badge ${trust.class}`;
    elements.detailHeadline.textContent = card.headline;
    elements.detailSourceAuthor.textContent = card.source_name || 'Unknown Source';
    elements.detailTime.textContent = formatTimeAgo(card.event_time || card.published_at);
    
    // Hide technical score from user
    if (elements.detailFinalScore) {
      elements.detailFinalScore.textContent = '';
      elements.detailFinalScore.style.display = 'none';
    }
    elements.detailPriorityReason.textContent = card.priority_reason || 'Verified and corroborated news report';

    // Subscores and bars
    const imp = Number(card.importance_score || 0).toFixed(1);
    const urg = Number(card.urgency_score || 0).toFixed(1);
    const frs = Number(card.freshness_score || 0).toFixed(1);
    const ver = Number(card.verification_score || 0).toFixed(1);
    const rel = Number(card.personal_relevance_score || 0).toFixed(1);

    elements.detailScoreImportance.textContent = `${imp}/100`;
    elements.detailScoreUrgency.textContent = `${urg}/100`;
    elements.detailScoreFreshness.textContent = `${frs}/100`;
    elements.detailScoreVerification.textContent = `${ver}/100`;
    elements.detailScoreRelevance.textContent = `${rel}/100`;

    elements.barImportance.style.width = `${Math.min(100, Math.max(0, imp))}%`;
    elements.barUrgency.style.width = `${Math.min(100, Math.max(0, urg))}%`;
    elements.barFreshness.style.width = `${Math.min(100, Math.max(0, frs))}%`;
    elements.barVerification.style.width = `${Math.min(100, Math.max(0, ver))}%`;
    elements.barRelevance.style.width = `${Math.min(100, Math.max(0, rel))}%`;

    // Summary
    elements.detailSummaryContent.innerHTML = `<p>${(card.summary || card.headline).replace(/\n\n/g, '</p><p>')}</p>`;

    // Sources
    elements.detailSourcesList.innerHTML = '';
    const sources = (card.sources && card.sources.length > 0) ? card.sources : (card.corroborating_sources || [
      { name: card.source_name || 'Primary Source', url: card.canonical_url || card.source_url }
    ]);

    sources.forEach((s) => {
      const li = document.createElement('li');
      li.innerHTML = `<a href="${s.url || '#'}" target="_blank" rel="noopener noreferrer">${s.name || 'Source Link'} &rarr;</a>`;
      elements.detailSourcesList.appendChild(li);
    });

    elements.btnOpenOriginalArticle.href = (sources[0] && sources[0].url) || card.canonical_url || card.source_url || '#';
    elements.modalDetail.classList.remove('hidden');
  }

  // --- Interest Preferences Modal Rendering ---
  function renderInterestChips() {
    elements.interestChipsContainer.innerHTML = '';
    ALL_CATEGORIES.forEach((cat, index) => {
      const isSelected = state.interests.includes(cat);
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = `interest-chip ${isSelected ? 'selected' : ''}`;
      chip.id = `chip-interest-${cat.toLowerCase()}`;
      chip.setAttribute('data-category', cat);
      chip.innerHTML = `
        <span class="chip-name">${cat}</span>
        <span class="chip-check">${isSelected ? '✓' : '+'}</span>
      `;

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

  // --- Priority Ranking Modal Rendering ---
  function syncPriorityOrderWithInterests() {
    if (!state.priorityOrder || state.priorityOrder.length === 0) {
      state.priorityOrder = [...state.interests];
      return;
    }
    // Keep only categories currently selected in interests
    state.priorityOrder = state.priorityOrder.filter(cat => state.interests.includes(cat));
    // Append any newly selected categories in interests that are not yet in priorityOrder
    state.interests.forEach(cat => {
      if (!state.priorityOrder.includes(cat)) {
        state.priorityOrder.push(cat);
      }
    });
  }

  function renderPriorityList() {
    syncPriorityOrderWithInterests();
    elements.priorityListContainer.innerHTML = '';
    elements.priorityErrorBanner.classList.add('hidden');

    if (state.priorityOrder.length === 0) {
      const emptyEl = document.createElement('div');
      emptyEl.className = 'priority-empty-msg';
      emptyEl.innerHTML = '<p>No categories selected. All news topics will be ranked with equal weight.</p>';
      elements.priorityListContainer.appendChild(emptyEl);
      return;
    }

    state.priorityOrder.forEach((cat, idx) => {
      const item = document.createElement('div');
      item.className = 'priority-item';
      item.id = `priority-item-${cat.toLowerCase()}`;
      item.setAttribute('data-category', cat);

      const left = document.createElement('div');
      left.className = 'priority-item-left';
      left.innerHTML = `
        <span class="priority-rank-badge">${idx + 1}</span>
        <span class="priority-name">${cat}</span>
      `;

      const actions = document.createElement('div');
      actions.className = 'priority-actions';

      const btnUp = document.createElement('button');
      btnUp.type = 'button';
      btnUp.className = 'btn-priority-move btn-move-up';
      btnUp.id = `btn-priority-up-${cat.toLowerCase()}`;
      btnUp.title = `Move ${cat} up`;
      btnUp.setAttribute('aria-label', `Move ${cat} up`);
      btnUp.textContent = '↑';
      if (idx === 0) {
        btnUp.disabled = true;
      }
      btnUp.addEventListener('click', (e) => {
        e.stopPropagation();
        if (idx > 0) {
          const temp = state.priorityOrder[idx];
          state.priorityOrder[idx] = state.priorityOrder[idx - 1];
          state.priorityOrder[idx - 1] = temp;
          renderPriorityList();
        }
      });

      const btnDown = document.createElement('button');
      btnDown.type = 'button';
      btnDown.className = 'btn-priority-move btn-move-down';
      btnDown.id = `btn-priority-down-${cat.toLowerCase()}`;
      btnDown.title = `Move ${cat} down`;
      btnDown.setAttribute('aria-label', `Move ${cat} down`);
      btnDown.textContent = '↓';
      if (idx === state.priorityOrder.length - 1) {
        btnDown.disabled = true;
      }
      btnDown.addEventListener('click', (e) => {
        e.stopPropagation();
        if (idx < state.priorityOrder.length - 1) {
          const temp = state.priorityOrder[idx];
          state.priorityOrder[idx] = state.priorityOrder[idx + 1];
          state.priorityOrder[idx + 1] = temp;
          renderPriorityList();
        }
      });

      actions.appendChild(btnUp);
      actions.appendChild(btnDown);

      item.appendChild(left);
      item.appendChild(actions);
      elements.priorityListContainer.appendChild(item);
    });
  }

  // --- Backend Preferences Sync ---
  async function savePriorityAndSyncBackend(isOnboardingRef, setOnboardingFalse) {
    elements.priorityErrorBanner.classList.add('hidden');
    elements.btnSavePriority.disabled = true;
    const originalBtnText = elements.btnSavePriority.textContent;
    elements.btnSavePriority.textContent = 'Saving priorities...';

    syncPriorityOrderWithInterests();
    const categoriesToSend = state.priorityOrder.map(c => c.toLowerCase());

    // 1. Immediately persist preferences in browser localStorage
    localStorage.setItem(STORAGE_KEYS.INTERESTS, JSON.stringify(state.interests));
    localStorage.setItem(STORAGE_KEYS.PRIORITY_ORDER, JSON.stringify(state.priorityOrder));
    localStorage.setItem(STORAGE_KEYS.ONBOARDING_COMPLETE, 'true');

    // 2. Hide modal and trigger feed rendering immediately
    elements.modalPriority.classList.add('hidden');
    if (typeof setOnboardingFalse === 'function') {
      setOnboardingFalse();
    }
    fetchFeed();

    // 3. Sync to backend in the background if API is available
    try {
      if (!window.location.hostname.includes('github.io')) {
        await fetch(`${API_BASE}/user/${encodeURIComponent(state.deviceId)}/preferences`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            category_order: categoriesToSend
          })
        });
      }
    } catch (err) {
      console.warn('Backend preferences sync failed (using local settings):', err);
    } finally {
      elements.btnSavePriority.disabled = false;
      elements.btnSavePriority.textContent = originalBtnText;
    }
  }

  // --- Event Listeners Setup ---
  function initEventListeners() {
    // Refresh button
    elements.btnRefresh.addEventListener('click', () => fetchFeed());

    // Category navigation tabs
    elements.categoryTabs.forEach(tab => {
      tab.addEventListener('click', () => {
        elements.categoryTabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        state.activeCategory = tab.getAttribute('data-category');
        _resetPagination();
        _detachScrollObserver();
        fetchFeed();
      });
    });

    // Reset from empty state
    elements.btnEmptyReset.addEventListener('click', () => {
      const allTab = document.getElementById('tab-category-all');
      if (allTab) allTab.click();
    });

    const isOnboardingComplete = localStorage.getItem(STORAGE_KEYS.ONBOARDING_COMPLETE) === 'true';
    let isOnboarding = !isOnboardingComplete;

    // Welcome modal
    if (!isOnboardingComplete) {
      elements.modalWelcome.classList.remove('hidden');
    }
    elements.btnWelcomeStart.addEventListener('click', () => {
      elements.modalWelcome.classList.add('hidden');
      isOnboarding = true;
      elements.inputState.value = state.state;
      elements.modalLocation.classList.remove('hidden');
    });

    // Location modal
    elements.btnOpenLocation.addEventListener('click', () => {
      elements.inputState.value = state.state;
      elements.modalLocation.classList.remove('hidden');
    });
    elements.btnCloseLocation.addEventListener('click', () => {
      elements.modalLocation.classList.add('hidden');
      if (isOnboarding) {
        elements.modalWelcome.classList.remove('hidden');
      }
    });
    elements.btnSaveLocation.addEventListener('click', () => {
      state.state = elements.inputState.value.trim();
      if (state.state) {
        localStorage.setItem(STORAGE_KEYS.LOCATION_STATE, state.state);
      } else {
        localStorage.removeItem(STORAGE_KEYS.LOCATION_STATE);
      }
      updateLocationBadge();
      elements.modalLocation.classList.add('hidden');
      if (isOnboarding) {
        renderInterestChips();
        elements.modalInterests.classList.remove('hidden');
      } else {
        _resetPagination();
        _detachScrollObserver();
        fetchFeed();
      }
    });
    elements.btnSkipLocation.addEventListener('click', () => {
      state.state = '';
      elements.inputState.value = '';
      localStorage.removeItem(STORAGE_KEYS.LOCATION_STATE);
      updateLocationBadge();
      elements.modalLocation.classList.add('hidden');
      if (isOnboarding) {
        renderInterestChips();
        elements.modalInterests.classList.remove('hidden');
      } else {
        _resetPagination();
        _detachScrollObserver();
        fetchFeed();
      }
    });

    // Interests modal
    elements.btnOpenInterests.addEventListener('click', () => {
      renderInterestChips();
      elements.modalInterests.classList.remove('hidden');
    });
    elements.btnCloseInterests.addEventListener('click', () => {
      elements.modalInterests.classList.add('hidden');
      if (isOnboarding) {
        elements.modalWelcome.classList.remove('hidden');
      }
    });
    elements.btnResetInterests.addEventListener('click', () => {
      state.interests = ['Technology', 'National', 'Business', 'Politics'];
      state.priorityOrder = ['Technology', 'National', 'Business', 'Politics'];
      renderInterestChips();
    });
    elements.btnSaveInterests.addEventListener('click', () => {
      localStorage.setItem(STORAGE_KEYS.INTERESTS, JSON.stringify(state.interests));
      syncPriorityOrderWithInterests();
      elements.modalInterests.classList.add('hidden');
      renderPriorityList();
      elements.modalPriority.classList.remove('hidden');
    });

    // Priority modal
    elements.btnClosePriority.addEventListener('click', () => {
      elements.modalPriority.classList.add('hidden');
      if (isOnboarding) {
        elements.modalWelcome.classList.remove('hidden');
      }
    });
    elements.btnBackPriority.addEventListener('click', () => {
      elements.modalPriority.classList.add('hidden');
      renderInterestChips();
      elements.modalInterests.classList.remove('hidden');
    });
    elements.btnSavePriority.addEventListener('click', () => {
      savePriorityAndSyncBackend(isOnboarding, () => {
        isOnboarding = false;
      });
    });

    // Story detail modal close
    elements.btnCloseDetail.addEventListener('click', () => {
      elements.modalDetail.classList.add('hidden');
    });

    // Close modals on backdrop click
    document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
      backdrop.addEventListener('click', (e) => {
        if (e.target === backdrop && backdrop.id !== 'modal-welcome') {
          backdrop.classList.add('hidden');
          if (isOnboarding) {
            elements.modalWelcome.classList.remove('hidden');
          }
        }
      });
    });

    // Close modals on Escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        const openModals = document.querySelectorAll('.modal-backdrop:not(.hidden)');
        openModals.forEach(m => {
          if (m.id !== 'modal-welcome') {
            m.classList.add('hidden');
            if (isOnboarding) {
              elements.modalWelcome.classList.remove('hidden');
            }
          }
        });
      }
    });
  }

  // --- Initial Boot ---
  function init() {
    updateLocationBadge();
    initEventListeners();
    if (localStorage.getItem(STORAGE_KEYS.ONBOARDING_COMPLETE) === 'true') {
      fetchFeed();
    }
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
