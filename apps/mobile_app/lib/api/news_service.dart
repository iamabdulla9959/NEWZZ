import 'dart:convert';
import 'package:flutter/services.dart' show rootBundle;
import 'package:dio/dio.dart';
import '../core/network/api_client.dart';
import '../models/card.dart';
import '../models/feed.dart';
import '../models/user_preferences.dart';

class NewsService {
  final Dio _dio;

  NewsService() : _dio = ApiClient().dio;

  // Named constructor for testing
  NewsService.withDio(this._dio);

  Future<FeedOut> getFeed({
    String? category,
    String? district,
    String? state,
    String? deviceId,
    int offset = 0,
    int limit = 20,
    bool refresh = false,
  }) async {
    try {
      final response = await _dio.get('/feed', queryParameters: {
        if (category != null && category.isNotEmpty) 'category': category,
        if (district != null && district.isNotEmpty) 'district': district,
        if (state != null && state.isNotEmpty) 'state': state,
        if (deviceId != null && deviceId.isNotEmpty) 'device_id': deviceId,
        'offset': offset,
        'limit': limit,
        if (refresh) 'refresh': 'true',
        't': DateTime.now().millisecondsSinceEpoch,
      });

      if (response.statusCode == 200) {
        final feedOut = FeedOut.fromJson(response.data as Map<String, dynamic>);
        if (feedOut.items.isNotEmpty) {
          return feedOut;
        }
      }
      return await _loadBundledFallback(category: category, state: state, offset: offset, limit: limit);
    } catch (_) {
      return await _loadBundledFallback(category: category, state: state, offset: offset, limit: limit);
    }
  }

  Future<FeedOut> _loadBundledFallback({
    String? category,
    String? state,
    int offset = 0,
    int limit = 20,
  }) async {
    try {
      final jsonStr = await rootBundle.loadString('assets/data/feed.json');
      final data = json.decode(jsonStr) as Map<String, dynamic>;
      final rawItems = data['items'] as List<dynamic>? ?? [];
      
      final lowerCat = category?.trim().toLowerCase();
      final isPolitics = lowerCat == 'politics';
      
      final filtered = rawItems.where((item) {
        if (item is! Map<String, dynamic>) return false;
        if (lowerCat != null && lowerCat != 'top stories') {
          final itemCat = (item['category'] as String? ?? '').trim().toLowerCase();
          if (isPolitics) {
            if (itemCat != 'politics' && itemCat != 'national') return false;
          } else if (itemCat != lowerCat) {
            return false;
          }
        }
        if (state != null && state.isNotEmpty && lowerCat == 'state') {
          final itemState = (item['state'] as String? ?? '').trim().toLowerCase();
          if (itemState.isNotEmpty && itemState != state.trim().toLowerCase()) return false;
        }
        return true;
      }).toList();

      final slice = filtered.skip(offset).take(limit).map((e) => CardOut.fromJson(e as Map<String, dynamic>)).toList();
      return FeedOut(
        items: slice,
        total: filtered.length,
        offset: offset,
        limit: limit,
      );
    } catch (_) {
      return FeedOut(items: [], total: 0, offset: offset, limit: limit);
    }
  }

  Future<void> triggerRefresh({String? state}) async {
    try {
      await _dio.get('/feed/refresh', queryParameters: {
        if (state != null && state.isNotEmpty) 'state': state,
      });
    } catch (_) {
      // Best effort background trigger
    }
  }

  Future<UserPreferencesOut> getUserPreferences(String deviceId) async {
    try {
      final response = await _dio.get('/user/$deviceId/preferences');
      if (response.statusCode == 200) {
        return UserPreferencesOut.fromJson(response.data as Map<String, dynamic>);
      } else {
        throw Exception('Failed to load preferences');
      }
    } catch (e) {
      throw Exception('Error loading preferences: $e');
    }
  }

  Future<UserPreferencesOut> updateUserPreferences(String deviceId, List<String> categoryOrder) async {
    try {
      final response = await _dio.put(
        '/user/$deviceId/preferences',
        data: {
          'category_order': categoryOrder,
        },
      );
      if (response.statusCode == 200) {
        return UserPreferencesOut.fromJson(response.data as Map<String, dynamic>);
      } else {
        throw Exception('Failed to update preferences');
      }
    } catch (e) {
      throw Exception('Error updating preferences: $e');
    }
  }
}
