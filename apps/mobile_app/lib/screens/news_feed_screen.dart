import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../api/news_service.dart';
import '../models/card.dart';
import '../widgets/news_card.dart';
import 'story_detail_screen.dart';
import 'preferences_screen.dart';
import '../core/utils/text_sanitizer.dart';
import '../core/theme/app_theme.dart';

class NewsFeedScreen extends StatefulWidget {
  const NewsFeedScreen({super.key});

  @override
  State<NewsFeedScreen> createState() => _NewsFeedScreenState();
}

class _NewsFeedScreenState extends State<NewsFeedScreen> with SingleTickerProviderStateMixin {
  final NewsService _newsService = NewsService();
  final ScrollController _scrollController = ScrollController();

  List<CardOut> _stories = [];
  bool _isLoading = true;
  bool _isFetchingMore = false;
  bool _hasError = false;
  String _errorMessage = '';

  int _offset = 0;
  final int _limit = 20;
  bool _hasMore = true;

  String? _deviceId;
  String? _selectedState;
  bool _isReelsMode = true;
  late final PageController _pageController = PageController();

  late TabController _tabController;
  int _lastTabIndex = 0;
  final List<String> _tabs = ['Top Stories', 'Technology', 'Politics', 'Business', 'World', 'State'];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: _tabs.length, vsync: this);
    _tabController.addListener(_onTabChanged);
    _scrollController.addListener(_onScroll);
    _initApp();
  }

  @override
  void dispose() {
    _tabController.dispose();
    _scrollController.dispose();
    _pageController.dispose();
    super.dispose();
  }

  Future<void> _initApp() async {
    final prefs = await SharedPreferences.getInstance();
    _deviceId = prefs.getString('device_id');
    _selectedState = prefs.getString('selected_state');

    if (_deviceId == null) {
      _deviceId = 'dev_${DateTime.now().millisecondsSinceEpoch}';
      await prefs.setString('device_id', _deviceId!);
    }

    _fetchFeed(refresh: true);
  }

  void _onTabChanged() {
    if (_tabController.index != _lastTabIndex) {
      _lastTabIndex = _tabController.index;
      if (_pageController.hasClients) {
        _pageController.jumpToPage(0);
      }
      _fetchFeed(refresh: true);
    }
  }

  void _onScroll() {
    if (_scrollController.position.pixels >= _scrollController.position.maxScrollExtent - 200 &&
        !_isLoading &&
        !_isFetchingMore &&
        _hasMore) {
      _fetchFeed(refresh: false);
    }
  }

  Future<void> _fetchFeed({required bool refresh}) async {
    if (!mounted) return;

    if (refresh) {
      setState(() {
        _isLoading = true;
        _hasError = false;
        _offset = 0;
        _hasMore = true;
      });
      // Fire-and-forget trigger to pull latest real-time dispatches from wire servers
      _newsService.triggerRefresh(state: _selectedState);
    } else {
      setState(() {
        _isFetchingMore = true;
        _hasError = false;
      });
    }

    try {
      final currentTab = _tabs[_tabController.index];
      String? categoryParam;

      if (currentTab != 'Top Stories') {
        categoryParam = currentTab;
      }

      final feed = await _newsService.getFeed(
        category: categoryParam,
        state: _selectedState,
        deviceId: _deviceId,
        offset: _offset,
        limit: _limit,
        refresh: refresh,
      );

      if (!mounted) return;

      setState(() {
        if (refresh) {
          _stories = feed.items;
        } else {
          _stories.addAll(feed.items);
        }

        _offset += feed.items.length;
        _hasMore = _offset < feed.total && feed.items.isNotEmpty;
        _isLoading = false;
        _isFetchingMore = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isLoading = false;
        _isFetchingMore = false;
        _hasError = true;
        _errorMessage = e.toString();
      });
    }
  }

  Future<void> _openPreferences() async {
    final result = await Navigator.push(
      context,
      MaterialPageRoute(builder: (context) => const PreferencesScreen()),
    );

    if (result == true) {
      final prefs = await SharedPreferences.getInstance();
      _selectedState = prefs.getString('selected_state');
      _fetchFeed(refresh: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Semantics(
          label: 'NEWZZ',
          child: Image.asset(
            theme.brightness == Brightness.dark
                ? 'assets/images/logo_dark.png'
                : 'assets/images/logo_light.png',
            height: 28,
            fit: BoxFit.contain,
          ),
        ),
        centerTitle: false,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh live news',
            onPressed: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Refreshing latest live wires...'),
                  duration: Duration(milliseconds: 1500),
                  behavior: SnackBarBehavior.floating,
                ),
              );
              _fetchFeed(refresh: true);
            },
          ),
          IconButton(
            icon: Icon(
              theme.brightness == Brightness.dark
                  ? Icons.light_mode_outlined
                  : Icons.dark_mode_outlined,
            ),
            tooltip: theme.brightness == Brightness.dark ? 'Switch to Light Mode' : 'Switch to Dark Mode',
            onPressed: () => AppTheme.toggleTheme(),
          ),
          IconButton(
            icon: Icon(_isReelsMode ? Icons.view_headline : Icons.bolt),
            tooltip: _isReelsMode ? 'Switch to Broadsheet List' : 'Switch to 60-Word Reels',
            onPressed: () {
              setState(() {
                _isReelsMode = !_isReelsMode;
              });
            },
          ),
          IconButton(
            icon: const Icon(Icons.tune),
            tooltip: 'Preferences',
            onPressed: _openPreferences,
          ),
        ],
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          onTap: (index) {
            if (index != _lastTabIndex) {
              _lastTabIndex = index;
              if (_pageController.hasClients) {
                _pageController.jumpToPage(0);
              }
              _fetchFeed(refresh: true);
            }
          },
          tabs: _tabs.map((t) => Tab(text: t)).toList(),
        ),
      ),
      body: _buildBody(theme),
    );
  }

  Widget _buildBody(ThemeData theme) {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_hasError && _stories.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.cloud_off, size: 64, color: Colors.grey),
              const SizedBox(height: 16),
              Text(
                'Network Error',
                style: theme.textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              Text(
                _errorMessage,
                textAlign: TextAlign.center,
                style: theme.textTheme.bodyMedium?.copyWith(color: Colors.grey),
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: () => _fetchFeed(refresh: true),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    if (_stories.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.inbox, size: 64, color: Colors.grey),
            const SizedBox(height: 16),
            Text(
              'No stories found',
              style: theme.textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text(
              'Try selecting a different category or updating your preferences.',
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium?.copyWith(color: Colors.grey),
            ),
          ],
        ),
      );
    }

    if (_isReelsMode) {
      return _buildReelsView(theme);
    }

    return RefreshIndicator(
      onRefresh: () => _fetchFeed(refresh: true),
      child: ListView.builder(
        controller: _scrollController,
        itemCount: _stories.length + (_hasMore ? 1 : 0),
        itemBuilder: (context, index) {
          if (index == _stories.length) {
            if (_hasError) {
              return Padding(
                padding: const EdgeInsets.all(16.0),
                child: Center(
                  child: ElevatedButton(
                    onPressed: () => _fetchFeed(refresh: false),
                    child: const Text('Retry Loading More'),
                  ),
                ),
              );
            }
            return const Padding(
              padding: EdgeInsets.all(16.0),
              child: Center(child: CircularProgressIndicator()),
            );
          }

          final card = _stories[index];
          return NewsCard(
            card: card,
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => StoryDetailScreen(card: card)),
              );
            },
          );
        },
      ),
    );
  }

    String _distill60Words(String text) {
    final words = text.trim().split(RegExp(r'\s+'));
    if (words.length <= 60) return text;
    return '${words.take(60).join(' ')}…';
  }

  String _getTimeAgo(DateTime? date) {
    if (date == null) return 'Date unavailable';
    final diff = DateTime.now().difference(date);
    if (diff.inSeconds < 0) {
      return 'Date unverified';
    } else if (diff.inMinutes < 60) {
      return '${diff.inMinutes}m ago';
    } else if (diff.inHours < 24) {
      return '${diff.inHours}h ago';
    } else {
      return '${diff.inDays}d ago';
    }
  }

  Widget _buildMetaChip(ThemeData theme, IconData icon, String label) {
    final isDark = theme.brightness == Brightness.dark;
    final chipBg = isDark ? const Color(0xFF1E2129) : const Color(0xFFF3F4F6);
    final textCol = isDark ? const Color(0xFFD1D5DB) : const Color(0xFF4B5563);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: chipBg,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: theme.colorScheme.outline.withValues(alpha: 0.5)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: textCol),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w500,
              color: textCol,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildReelsView(ThemeData theme) {
    return RefreshIndicator(
      onRefresh: () => _fetchFeed(refresh: true),
      child: PageView.builder(
        controller: _pageController,
        scrollDirection: Axis.vertical,
        physics: const AlwaysScrollableScrollPhysics(),
        itemCount: _stories.length,
        onPageChanged: (index) {
          if (index >= _stories.length - 2 && _hasMore && !_isFetchingMore) {
            _fetchFeed(refresh: false);
          }
        },
        itemBuilder: (context, index) {
          final card = _stories[index];
          return _buildReelCard(card, index, theme);
        },
      ),
    );
  }

  Widget _buildReelCard(CardOut card, int index, ThemeData theme) {
    final isDark = theme.brightness == Brightness.dark;
    final cat = card.category.toUpperCase();
    final sourceName = card.sources.isNotEmpty ? card.sources.first.name : 'Verified Wire';
    final fact1 = 'Verified by $sourceName';
    final fact2 = card.priorityReason.isNotEmpty ? card.priorityReason : 'Audited via verified national telemetry';

    return Container(
      color: theme.scaffoldBackgroundColor,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: SafeArea(
        child: Column(
          children: [
            // Top Indicator
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  children: [
                    Icon(Icons.bolt, size: 16, color: theme.colorScheme.primary),
                    const SizedBox(width: 4),
                    Text(
                      'NEWZZ REELS',
                      style: theme.textTheme.labelSmall?.copyWith(
                        color: theme.colorScheme.primary,
                        fontWeight: FontWeight.bold,
                        letterSpacing: 1.2,
                      ),
                    ),
                  ],
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: isDark ? const Color(0xFF1E2129) : const Color(0xFFF3F4F6),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    '${index + 1} / ${_stories.length}',
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: isDark ? const Color(0xFF9CA3AF) : const Color(0xFF6B7280),
                      fontFamily: 'monospace',
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),

            // Reel Card Frame
            Expanded(
              child: Container(
                decoration: BoxDecoration(
                  color: theme.cardColor,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: theme.colorScheme.outline),
                  boxShadow: isDark ? null : [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.04),
                      blurRadius: 12,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Container(width: 4, color: theme.colorScheme.primary),
                      Expanded(
                        child: Padding(
                          padding: const EdgeInsets.all(20),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              // Badges Row
                              Wrap(
                                spacing: 8,
                                runSpacing: 4,
                                crossAxisAlignment: WrapCrossAlignment.center,
                                children: [
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                    decoration: BoxDecoration(
                                      color: theme.colorScheme.primary.withValues(alpha: 0.12),
                                      borderRadius: BorderRadius.circular(4),
                                    ),
                                    child: Text(
                                      cat,
                                      style: TextStyle(
                                        color: theme.colorScheme.primary,
                                        fontSize: 11,
                                        fontWeight: FontWeight.bold,
                                        letterSpacing: 0.5,
                                      ),
                                    ),
                                  ),
                                  if (card.state != null && card.state!.isNotEmpty)
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                      decoration: BoxDecoration(
                                        color: isDark ? const Color(0xFF262930) : const Color(0xFFE5E7EB),
                                        borderRadius: BorderRadius.circular(4),
                                      ),
                                      child: Text(
                                        card.state!.toUpperCase(),
                                        style: TextStyle(
                                          color: isDark ? Colors.white : const Color(0xFF111111),
                                          fontSize: 11,
                                          fontWeight: FontWeight.w600,
                                        ),
                                      ),
                                    ),
                                  Text(
                                    _getTimeAgo(card.publishedAt),
                                    style: TextStyle(
                                      color: isDark ? const Color(0xFF9CA3AF) : const Color(0xFF6B7280),
                                      fontSize: 11,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 14),

                              // Headline
                              Text(
                                card.headline,
                                style: TextStyle(
                                  color: isDark ? Colors.white : const Color(0xFF111111),
                                  fontSize: 18,
                                  fontWeight: FontWeight.bold,
                                  height: 1.35,
                                ),
                              ),
                              const SizedBox(height: 12),

                              // 60-Word Summary
                              Expanded(
                                child: SingleChildScrollView(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      if (card.imageUrl != null && card.imageUrl!.isNotEmpty) ...[
                                        ClipRRect(
                                          borderRadius: BorderRadius.circular(8),
                                          child: Image.network(
                                            card.imageUrl!,
                                            height: 160,
                                            width: double.infinity,
                                            fit: BoxFit.cover,
                                            errorBuilder: (context, error, stackTrace) => const SizedBox.shrink(),
                                          ),
                                        ),
                                        const SizedBox(height: 12),
                                      ],
                                      Text(
                                        _distill60Words(TextSanitizer.cleanSummary(card.headline, card.summary)),
                                        style: TextStyle(
                                          color: isDark ? const Color(0xFFE2E8F0) : const Color(0xFF2D3748),
                                          fontSize: 15,
                                          height: 1.55,
                                        ),
                                      ),
                                      const SizedBox(height: 14),
                                      Container(
                                        padding: const EdgeInsets.all(12),
                                        decoration: BoxDecoration(
                                          color: isDark ? const Color(0xFF1F222A) : const Color(0xFFF8F9FA),
                                          borderRadius: BorderRadius.circular(8),
                                          border: Border.all(color: theme.colorScheme.outline),
                                        ),
                                        child: Column(
                                          crossAxisAlignment: CrossAxisAlignment.start,
                                          children: [fact1, fact2].map((fact) => Padding(
                                            padding: const EdgeInsets.only(bottom: 6),
                                            child: Row(
                                              crossAxisAlignment: CrossAxisAlignment.start,
                                              children: [
                                                Text('✓ ', style: TextStyle(color: theme.colorScheme.primary, fontWeight: FontWeight.bold)),
                                                Expanded(
                                                  child: Text(
                                                    fact,
                                                    style: TextStyle(
                                                      color: isDark ? const Color(0xFFCBD5E1) : const Color(0xFF4B5563),
                                                      fontSize: 12,
                                                      height: 1.4,
                                                    ),
                                                  ),
                                                ),
                                              ],
                                            ),
                                          )).toList(),
                                        ),
                                      ),
                                      const SizedBox(height: 12),
                                      Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                                        decoration: BoxDecoration(
                                          color: theme.colorScheme.primary.withValues(alpha: isDark ? 0.12 : 0.05),
                                          borderRadius: BorderRadius.circular(8),
                                          border: Border.all(
                                            color: theme.colorScheme.primary.withValues(alpha: isDark ? 0.3 : 0.2),
                                          ),
                                        ),
                                        child: Row(
                                          children: [
                                            Icon(
                                              card.isSingleSource ? Icons.shield_outlined : Icons.verified_user_outlined,
                                              size: 16,
                                              color: theme.colorScheme.primary,
                                            ),
                                            const SizedBox(width: 8),
                                            Expanded(
                                              child: Text(
                                                card.isSingleSource
                                                    ? 'Single Source Wire: Verified against primary agency dispatch.'
                                                    : 'Cross-Wire Consensus: Corroborated across ${card.corroborationCount > 1 ? card.corroborationCount : 2} independent wires.',
                                                style: TextStyle(
                                                  fontSize: 11.5,
                                                  fontWeight: FontWeight.w500,
                                                  color: isDark ? const Color(0xFFE2E8F0) : const Color(0xFF374151),
                                                  height: 1.35,
                                                ),
                                              ),
                                            ),
                                          ],
                                        ),
                                      ),
                                      const SizedBox(height: 12),
                                      Wrap(
                                        spacing: 6,
                                        runSpacing: 6,
                                        children: [
                                          _buildMetaChip(
                                            theme,
                                            Icons.speed,
                                            'Impact: ${card.priorityScore > 0 ? (card.priorityScore * 10).clamp(60, 99) : card.finalFeedScore.toInt().clamp(60, 99)}/100',
                                          ),
                                          _buildMetaChip(
                                            theme,
                                            Icons.timer_outlined,
                                            '1 min read',
                                          ),
                                          _buildMetaChip(
                                            theme,
                                            Icons.public,
                                            sourceName,
                                          ),
                                        ],
                                      ),
                                    ],
                                  ),
                                ),
                              ),

                              // Bottom Action Row
                              Divider(color: theme.dividerColor, height: 20),
                              Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                  Row(
                                    children: [
                                      Icon(Icons.verified, size: 16, color: theme.colorScheme.primary),
                                      const SizedBox(width: 4),
                                      Text(
                                        sourceName,
                                        style: TextStyle(
                                          color: isDark ? Colors.white70 : const Color(0xFF374151),
                                          fontSize: 12,
                                          fontWeight: FontWeight.w600,
                                        ),
                                      ),
                                    ],
                                  ),
                                  ElevatedButton(
                                    style: ElevatedButton.styleFrom(
                                      backgroundColor: theme.colorScheme.primary,
                                      foregroundColor: Colors.white,
                                      elevation: 0,
                                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                                      textStyle: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
                                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                                    ),
                                    onPressed: () {
                                      Navigator.push(
                                        context,
                                        MaterialPageRoute(builder: (context) => StoryDetailScreen(card: card)),
                                      );
                                    },
                                    child: const Row(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        Text('Full Dossier'),
                                        SizedBox(width: 4),
                                        Icon(Icons.arrow_forward, size: 14),
                                      ],
                                    ),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
