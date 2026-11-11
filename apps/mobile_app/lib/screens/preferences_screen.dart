import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../api/news_service.dart';

class PreferencesScreen extends StatefulWidget {
  const PreferencesScreen({super.key});

  @override
  State<PreferencesScreen> createState() => _PreferencesScreenState();
}

class _PreferencesScreenState extends State<PreferencesScreen> {
  final _newsService = NewsService();
  bool _isLoading = true;
  String? _deviceId;

  final List<String> _availableCategories = [
    'Technology', 'Politics', 'Business', 'National', 'World',
    'Science', 'Health', 'Sports', 'Entertainment', 'Environment'
  ];

  List<String> _selectedCategories = [];
  String? _selectedState;

  final List<String> _states = [
    // 28 Indian States
    'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh',
    'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jharkhand',
    'Karnataka', 'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Manipur',
    'Meghalaya', 'Mizoram', 'Nagaland', 'Odisha', 'Punjab',
    'Rajasthan', 'Sikkim', 'Tamil Nadu', 'Telangana', 'Tripura',
    'Uttar Pradesh', 'Uttarakhand', 'West Bengal',
    // 8 Union Territories
    'Andaman and Nicobar Islands', 'Chandigarh',
    'Dadra and Nagar Haveli and Daman and Diu', 'Delhi',
    'Jammu and Kashmir', 'Ladakh', 'Lakshadweep', 'Puducherry'
  ];

  @override
  void initState() {
    super.initState();
    _loadPreferences();
  }

  Future<void> _loadPreferences() async {
    final prefs = await SharedPreferences.getInstance();
    String? deviceId = prefs.getString('device_id');

    if (deviceId == null) {
      deviceId = 'dev_${DateTime.now().millisecondsSinceEpoch}';
      await prefs.setString('device_id', deviceId);
    }

    _selectedState = prefs.getString('selected_state');

    try {
      final userPrefs = await _newsService.getUserPreferences(deviceId);
      if (mounted) {
        setState(() {
          _deviceId = deviceId;
          _selectedCategories = List<String>.from(userPrefs.categoryOrder);
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _deviceId = deviceId;
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _savePreferences() async {
    if (_deviceId == null) return;

    setState(() => _isLoading = true);

    try {
      final prefs = await SharedPreferences.getInstance();
      if (_selectedState != null) {
        await prefs.setString('selected_state', _selectedState!);
      } else {
        await prefs.remove('selected_state');
      }

      await _newsService.updateUserPreferences(_deviceId!, _selectedCategories);

      if (mounted) {
        Navigator.pop(context, true);
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to save preferences: $e')),
        );
      }
    }
  }

  void _toggleCategory(String category) {
    setState(() {
      if (_selectedCategories.contains(category)) {
        _selectedCategories.remove(category);
      } else {
        _selectedCategories.add(category);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Preferences'),
        actions: [
          if (!_isLoading)
            IconButton(
              icon: const Icon(Icons.check),
              onPressed: _savePreferences,
            ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Text('Regional News', style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                Text('Select your state to prioritize local news.', style: theme.textTheme.bodyMedium),
                const SizedBox(height: 16),
                DropdownButtonFormField<String>(
                  initialValue: _selectedState,
                  decoration: const InputDecoration(
                    labelText: 'State',
                    border: OutlineInputBorder(),
                  ),
                  items: [
                    const DropdownMenuItem<String>(
                      value: null,
                      child: Text('None (National/Global only)'),
                    ),
                    ..._states.map((s) => DropdownMenuItem(value: s, child: Text(s))),
                  ],
                  onChanged: (val) {
                    setState(() {
                      _selectedState = val;
                    });
                  },
                ),
                const SizedBox(height: 32),
                Text('Favorite Categories', style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                Text('Select categories you want to see more often.', style: theme.textTheme.bodyMedium),
                const SizedBox(height: 16),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: _availableCategories.map((cat) {
                    final isSelected = _selectedCategories.contains(cat);
                    return FilterChip(
                      label: Text(cat),
                      selected: isSelected,
                      onSelected: (_) => _toggleCategory(cat),
                      selectedColor: theme.colorScheme.primary.withValues(alpha: 0.2),
                      checkmarkColor: theme.colorScheme.primary,
                    );
                  }).toList(),
                ),
              ],
            ),
    );
  }
}
