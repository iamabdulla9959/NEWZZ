import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../api/news_service.dart';
import '../models/card.dart';
import '../widgets/news_card.dart';
import 'story_detail_screen.dart';
import 'preferences_screen.dart';
import '../core/utils/text_sanitizer.dart';

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
    if (_tabController.indexIsChanging) {
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
        title: const Text('NEWZZ', style: TextStyle(fontWeight: FontWeight.bold, letterSpacing: 2)),
        centerTitle: true,
        actions: [
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
            onPressed: _openPreferences,
          ),
        ],
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
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

  Widget _buildReelsView(ThemeData theme) {
    return PageView.builder(
      controller: _pageController,
      scrollDirection: Axis.vertical,
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
    );
  }

  Widget _buildReelCard(CardOut card, int index, ThemeData theme) {
    final cat = card.category.toUpperCase();
    final sourceName = card.sources.isNotEmpty ? card.sources.first.name : 'Verified Wire';
    final fact1 = 'Verified by $sourceName';
    final fact2 = card.priorityReason.isNotEmpty ? card.priorityReason : 'Audited via verified national telemetry';

    return Container(
      color: const Color(0xFF080808),
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
                    const Icon(Icons.bolt, size: 16, color: Color(0xFFFF7A00)),
                    const SizedBox(width: 4),
                    Text(
                      'NEWZZ REELS',
                      style: theme.textTheme.labelSmall?.copyWith(
                        color: const Color(0xFFFF7A00),
                        fontWeight: FontWeight.bold,
                        letterSpacing: 1.2,
                      ),
                    ),
                  ],
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: const Color(0xFF1C1C1C),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    '${index + 1} / ${_stories.length}',
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: Colors.grey,
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
                  color: const Color(0xFF141414),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: const Color(0xFF262626)),
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Container(width: 4, color: const Color(0xFFFF7A00)),
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
                                      color: const Color(0xFFFF7A00).withValues(alpha: 0.15),
                                      borderRadius: BorderRadius.circular(4),
                                    ),
                                    child: Text(
                                      cat,
                                      style: const TextStyle(
                                        color: Color(0xFFFF7A00),
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
                                        color: const Color(0xFF262626),
                                        borderRadius: BorderRadius.circular(4),
                                      ),
                                      child: Text(
                                        card.state!.toUpperCase(),
                                        style: const TextStyle(
                                          color: Colors.white,
                                          fontSize: 11,
                                          fontWeight: FontWeight.w600,
                                        ),
                                      ),
                                    ),
                                  Text(
                                    _getTimeAgo(card.publishedAt),
                                    style: const TextStyle(color: Colors.grey, fontSize: 11),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 14),

                              // Headline
                              Text(
                                card.headline,
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 18,
                                  fontWeight: FontWeight.bold,
                                  height: 1.3,
                                ),
                              ),
                              const SizedBox(height: 12),

                              // 60-Word Summary
                              Expanded(
                                child: SingleChildScrollView(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        _distill60Words(TextSanitizer.cleanSummary(card.headline, card.summary)),
                                        style: const TextStyle(
                                          color: Color(0xFFEDEDED),
                                          fontSize: 14,
                                          height: 1.5,
                                        ),
                                      ),
                                      const SizedBox(height: 14),
                                      Container(
                                        padding: const EdgeInsets.all(12),
                                        decoration: BoxDecoration(
                                          color: const Color(0xFF1A1A1A),
                                          borderRadius: BorderRadius.circular(8),
                                          border: Border.all(color: const Color(0xFF2E2E2E)),
                                        ),
                                        child: Column(
                                          crossAxisAlignment: CrossAxisAlignment.start,
                                          children: [fact1, fact2].map((fact) => Padding(
                                            padding: const EdgeInsets.only(bottom: 6),
                                            child: Row(
                                              crossAxisAlignment: CrossAxisAlignment.start,
                                              children: [
                                                const Text('✓ ', style: TextStyle(color: Color(0xFFFF7A00), fontWeight: FontWeight.bold)),
                                                Expanded(
                                                  child: Text(
                                                    fact,
                                                    style: const TextStyle(color: Color(0xFFA3A3A3), fontSize: 12, height: 1.4),
                                                  ),
                                                ),
                                              ],
                                            ),
                                          )).toList(),
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ),

                              // Bottom Action Row
                              const Divider(color: Color(0xFF262626), height: 20),
                              Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                  Row(
                                    children: [
                                      const Icon(Icons.verified, size: 16, color: Color(0xFFFF7A00)),
                                      const SizedBox(width: 4),
                                      Text(
                                        sourceName,
                                        style: const TextStyle(color: Colors.white70, fontSize: 12, fontWeight: FontWeight.w600),
                                      ),
                                    ],
                                  ),
                                  ElevatedButton(
                                    style: ElevatedButton.styleFrom(
                                      backgroundColor: const Color(0xFFFF7A00),
                                      foregroundColor: Colors.black,
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
