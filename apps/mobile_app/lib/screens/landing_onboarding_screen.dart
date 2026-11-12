import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'news_feed_screen.dart';

class LandingOnboardingScreen extends StatefulWidget {
  const LandingOnboardingScreen({super.key});

  @override
  State<LandingOnboardingScreen> createState() => _LandingOnboardingScreenState();
}

class _LandingOnboardingScreenState extends State<LandingOnboardingScreen> {
  final PageController _pageController = PageController();
  int _currentPage = 0;

  String? _selectedState = 'Telangana';
  final Set<String> _selectedTopics = {'Top Stories', 'Technology', 'Politics', 'Business'};

  final List<String> _popularStates = [
    'All India (National)',
    'Telangana',
    'Andhra Pradesh',
    'Karnataka',
    'Maharashtra',
    'Delhi',
    'Tamil Nadu',
    'Uttar Pradesh',
    'Kerala',
    'Gujarat',
    'West Bengal',
    'Punjab',
    'Rajasthan',
    'Madhya Pradesh',
    'Bihar',
    'Odisha',
  ];

  final List<Map<String, String>> _topics = [
    {'name': 'Top Stories', 'icon': '⚡'},
    {'name': 'Politics', 'icon': '🏛️'},
    {'name': 'Technology', 'icon': '💻'},
    {'name': 'Business', 'icon': '📈'},
    {'name': 'World', 'icon': '🌍'},
    {'name': 'Science', 'icon': '🔬'},
    {'name': 'Sports', 'icon': '🏏'},
    {'name': 'Environment', 'icon': '🌱'},
  ];

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  Future<void> _completeOnboarding() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('has_completed_onboarding', true);

    if (_selectedState != null && _selectedState != 'All India (National)') {
      await prefs.setString('selected_state', _selectedState!);
    } else {
      await prefs.remove('selected_state');
    }

    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (context) => const NewsFeedScreen()),
    );
  }

  void _nextPage() {
    if (_currentPage < 2) {
      _pageController.nextPage(
        duration: const Duration(milliseconds: 350),
        curve: Curves.easeInOut,
      );
    } else {
      _completeOnboarding();
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      body: SafeArea(
        child: Column(
          children: [
            // Top Bar with Skip Button
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Semantics(
                    label: 'NEWZZ',
                    child: Image.asset(
                      isDark ? 'assets/images/logo_dark.png' : 'assets/images/logo_light.png',
                      height: 24,
                      fit: BoxFit.contain,
                    ),
                  ),
                  if (_currentPage < 2)
                    TextButton(
                      onPressed: _completeOnboarding,
                      child: Text(
                        'Skip',
                        style: TextStyle(
                          color: isDark ? const Color(0xFF9CA3AF) : const Color(0xFF6B7280),
                          fontSize: 14,
                        ),
                      ),
                    ),
                ],
              ),
            ),

            // Page Indicator
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: List.generate(3, (index) {
                final isSelected = _currentPage == index;
                return AnimatedContainer(
                  duration: const Duration(milliseconds: 250),
                  margin: const EdgeInsets.symmetric(horizontal: 4),
                  width: isSelected ? 24 : 8,
                  height: 4,
                  decoration: BoxDecoration(
                    color: isSelected ? theme.colorScheme.primary : (isDark ? const Color(0xFF262930) : const Color(0xFFE5E7EB)),
                    borderRadius: BorderRadius.circular(2),
                  ),
                );
              }),
            ),

            // Main Content Pages
            Expanded(
              child: PageView(
                controller: _pageController,
                onPageChanged: (index) {
                  setState(() {
                    _currentPage = index;
                  });
                },
                children: [
                  _buildWelcomePage(theme, isDark),
                  _buildStateSelectionPage(theme, isDark),
                  _buildTopicsPage(theme, isDark),
                ],
              ),
            ),

            // Bottom Navigation Button
            Padding(
              padding: const EdgeInsets.all(24),
              child: SizedBox(
                width: double.infinity,
                height: 52,
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: theme.colorScheme.primary,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                    elevation: 0,
                  ),
                  onPressed: _nextPage,
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        _currentPage == 2 ? 'Enter NEWZZ' : 'Continue',
                        style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(width: 8),
                      const Icon(Icons.arrow_forward, size: 18),
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

  // Page 1: Welcome & Value Prop
  Widget _buildWelcomePage(ThemeData theme, bool isDark) {
    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: isDark ? const Color(0xFF181A20) : const Color(0xFFF9FAFB),
              shape: BoxShape.circle,
              border: Border.all(
                color: theme.colorScheme.primary.withValues(alpha: 0.25),
                width: 2,
              ),
              boxShadow: isDark ? null : [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.05),
                  blurRadius: 16,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Image.asset(
              'assets/images/app_icon_mark.png',
              height: 64,
              width: 64,
              fit: BoxFit.contain,
            ),
          ),
          const SizedBox(height: 24),
          Text(
            'Real News. 60 Words. Zero Ads.',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: isDark ? Colors.white : const Color(0xFF111111),
              fontSize: 26,
              fontWeight: FontWeight.bold,
              height: 1.25,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            'Instant, fact-checked news capsules distilled from trusted national wires, free from clickbait and intrusive advertising.',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: isDark ? const Color(0xFFA0AEC0) : const Color(0xFF4B5563),
              fontSize: 14,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 36),
          _buildFeatureRow(
            theme: theme,
            isDark: isDark,
            icon: Icons.view_carousel,
            title: '60-Word Vertical Reels',
            subtitle: 'Swipe through breaking affairs with zero lag or clutter.',
          ),
          const SizedBox(height: 16),
          _buildFeatureRow(
            theme: theme,
            isDark: isDark,
            icon: Icons.verified_user_outlined,
            title: 'Verified Provenance',
            subtitle: 'Audited across Tier-1 wires including The Hindu, Reuters, and TOI.',
          ),
          const SizedBox(height: 16),
          _buildFeatureRow(
            theme: theme,
            isDark: isDark,
            icon: Icons.block,
            title: '100% Ad-Free Experience',
            subtitle: 'No commercial popups, no video ads, no sponsored distraction.',
          ),
        ],
      ),
    );
  }

  Widget _buildFeatureRow({
    required ThemeData theme,
    required bool isDark,
    required IconData icon,
    required String title,
    required String subtitle,
  }) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF181A20) : const Color(0xFFFFFFFF),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: theme.colorScheme.outline),
        boxShadow: isDark ? null : [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.03),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: theme.colorScheme.primary.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(icon, color: theme.colorScheme.primary, size: 22),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    color: isDark ? Colors.white : const Color(0xFF111111),
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: TextStyle(
                    color: isDark ? const Color(0xFF9CA3AF) : const Color(0xFF6B7280),
                    fontSize: 12,
                    height: 1.3,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // Page 2: State Selection
  Widget _buildStateSelectionPage(ThemeData theme, bool isDark) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Select Your Region',
            style: TextStyle(
              color: isDark ? Colors.white : const Color(0xFF111111),
              fontSize: 24,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            'Get localized governance, district alerts, and policy updates tailored to your home state.',
            style: TextStyle(
              color: isDark ? const Color(0xFF9CA3AF) : const Color(0xFF6B7280),
              fontSize: 14,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 18),
          Expanded(
            child: ListView.separated(
              itemCount: _popularStates.length,
              separatorBuilder: (_, index) => const SizedBox(height: 8),
              itemBuilder: (context, index) {
                final st = _popularStates[index];
                final isSelected = _selectedState == st ||
                    (_selectedState == null && st == 'All India (National)');

                return InkWell(
                  onTap: () {
                    setState(() {
                      _selectedState = st;
                    });
                  },
                  borderRadius: BorderRadius.circular(8),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                    decoration: BoxDecoration(
                      color: isSelected
                          ? (isDark ? const Color(0xFF2B161A) : const Color(0xFFFEF2F2))
                          : (isDark ? const Color(0xFF181A20) : const Color(0xFFFFFFFF)),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: isSelected ? theme.colorScheme.primary : theme.colorScheme.outline,
                        width: isSelected ? 1.5 : 1,
                      ),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          st,
                          style: TextStyle(
                            color: isSelected
                                ? theme.colorScheme.primary
                                : (isDark ? const Color(0xFFE5E7EB) : const Color(0xFF1F2937)),
                            fontSize: 15,
                            fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                          ),
                        ),
                        if (isSelected)
                          Icon(Icons.check_circle, color: theme.colorScheme.primary, size: 20),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  // Page 3: Topics Selection
  Widget _buildTopicsPage(ThemeData theme, bool isDark) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Choose Your Topics',
            style: TextStyle(
              color: isDark ? Colors.white : const Color(0xFF111111),
              fontSize: 24,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            'Tap the news categories you follow most closely to customize your feed prioritization.',
            style: TextStyle(
              color: isDark ? const Color(0xFF9CA3AF) : const Color(0xFF6B7280),
              fontSize: 14,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 24),
          Expanded(
            child: GridView.builder(
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                crossAxisSpacing: 12,
                mainAxisSpacing: 12,
                childAspectRatio: 2.2,
              ),
              itemCount: _topics.length,
              itemBuilder: (context, index) {
                final top = _topics[index];
                final name = top['name']!;
                final icon = top['icon']!;
                final isSelected = _selectedTopics.contains(name);

                return InkWell(
                  onTap: () {
                    setState(() {
                      if (isSelected) {
                        if (_selectedTopics.length > 1) {
                          _selectedTopics.remove(name);
                        }
                      } else {
                        _selectedTopics.add(name);
                      }
                    });
                  },
                  borderRadius: BorderRadius.circular(8),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                    decoration: BoxDecoration(
                      color: isSelected
                          ? (isDark ? const Color(0xFF2B161A) : const Color(0xFFFEF2F2))
                          : (isDark ? const Color(0xFF181A20) : const Color(0xFFFFFFFF)),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: isSelected ? theme.colorScheme.primary : theme.colorScheme.outline,
                        width: isSelected ? 1.5 : 1,
                      ),
                    ),
                    child: Row(
                      children: [
                        Text(icon, style: const TextStyle(fontSize: 20)),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            name,
                            style: TextStyle(
                              color: isSelected
                                  ? theme.colorScheme.primary
                                  : (isDark ? const Color(0xFFE5E7EB) : const Color(0xFF1F2937)),
                              fontSize: 14,
                              fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
