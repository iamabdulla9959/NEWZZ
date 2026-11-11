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
    return Scaffold(
      backgroundColor: const Color(0xFF080808),
      body: SafeArea(
        child: Column(
          children: [
            // Top Bar with Skip Button
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Row(
                    children: [
                      Container(
                        width: 8,
                        height: 8,
                        decoration: const BoxDecoration(
                          color: Color(0xFFFF7A00),
                          shape: BoxShape.circle,
                        ),
                      ),
                      const SizedBox(width: 8),
                      const Text(
                        'NEWZZ',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                          letterSpacing: 2,
                        ),
                      ),
                    ],
                  ),
                  if (_currentPage < 2)
                    TextButton(
                      onPressed: _completeOnboarding,
                      child: const Text(
                        'Skip',
                        style: TextStyle(color: Colors.grey, fontSize: 14),
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
                    color: isSelected ? const Color(0xFFFF7A00) : const Color(0xFF262626),
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
                  _buildWelcomePage(),
                  _buildStateSelectionPage(),
                  _buildTopicsPage(),
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
                    backgroundColor: const Color(0xFFFF7A00),
                    foregroundColor: Colors.black,
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
  Widget _buildWelcomePage() {
    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: const Color(0xFF141414),
              shape: BoxShape.circle,
              border: Border.all(color: const Color(0xFFFF7A00).withValues(alpha: 0.3), width: 2),
            ),
            child: const Icon(
              Icons.bolt,
              size: 56,
              color: Color(0xFFFF7A00),
            ),
          ),
          const SizedBox(height: 24),
          const Text(
            'Real News. 60 Words. Zero Ads.',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: Colors.white,
              fontSize: 26,
              fontWeight: FontWeight.bold,
              height: 1.25,
            ),
          ),
          const SizedBox(height: 12),
          const Text(
            'Instant, fact-checked news capsules distilled from trusted national wires, free from clickbait and intrusive advertising.',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: Color(0xFFA3A3A3),
              fontSize: 14,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 36),
          _buildFeatureRow(
            icon: Icons.view_carousel,
            title: '60-Word Vertical Reels',
            subtitle: 'Swipe through breaking affairs with zero lag or clutter.',
          ),
          const SizedBox(height: 16),
          _buildFeatureRow(
            icon: Icons.verified_user_outlined,
            title: 'Verified Provenance',
            subtitle: 'Audited across Tier-1 wires including The Hindu, Reuters, and TOI.',
          ),
          const SizedBox(height: 16),
          _buildFeatureRow(
            icon: Icons.block,
            title: '100% Ad-Free Experience',
            subtitle: 'No commercial popups, no video ads, no sponsored distraction.',
          ),
        ],
      ),
    );
  }

  Widget _buildFeatureRow({required IconData icon, required String title, required String subtitle}) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF141414),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFF262626)),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: const Color(0xFFFF7A00).withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(icon, color: const Color(0xFFFF7A00), size: 22),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: const TextStyle(color: Colors.grey, fontSize: 12, height: 1.3),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // Page 2: State Selection
  Widget _buildStateSelectionPage() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Select Your Region',
            style: TextStyle(
              color: Colors.white,
              fontSize: 24,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 6),
          const Text(
            'Get localized governance, district alerts, and policy updates tailored to your home state.',
            style: TextStyle(color: Colors.grey, fontSize: 14, height: 1.4),
          ),
          const SizedBox(height: 18),
          Expanded(
            child: ListView.separated(
              itemCount: _popularStates.length,
              separatorBuilder: (_, __) => const SizedBox(height: 8),
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
                      color: isSelected ? const Color(0xFF1F1810) : const Color(0xFF141414),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: isSelected ? const Color(0xFFFF7A00) : const Color(0xFF262626),
                        width: isSelected ? 1.5 : 1,
                      ),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          st,
                          style: TextStyle(
                            color: isSelected ? Colors.white : const Color(0xFFD4D4D4),
                            fontSize: 15,
                            fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                          ),
                        ),
                        if (isSelected)
                          const Icon(Icons.check_circle, color: Color(0xFFFF7A00), size: 20),
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
  Widget _buildTopicsPage() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Choose Your Topics',
            style: TextStyle(
              color: Colors.white,
              fontSize: 24,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 6),
          const Text(
            'Tap the news categories you follow most closely to customize your feed prioritization.',
            style: TextStyle(color: Colors.grey, fontSize: 14, height: 1.4),
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
                      color: isSelected ? const Color(0xFF1F1810) : const Color(0xFF141414),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: isSelected ? const Color(0xFFFF7A00) : const Color(0xFF262626),
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
                              color: isSelected ? Colors.white : const Color(0xFFD4D4D4),
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
