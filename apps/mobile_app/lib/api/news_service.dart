import 'package:dio/dio.dart';
import '../core/network/api_client.dart';
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
  }) async {
    try {
      final response = await _dio.get('/feed', queryParameters: {
        if (category != null && category.isNotEmpty) 'category': category,
        if (district != null && district.isNotEmpty) 'district': district,
        if (state != null && state.isNotEmpty) 'state': state,
        if (deviceId != null && deviceId.isNotEmpty) 'device_id': deviceId,
        'offset': offset,
        'limit': limit,
      });

      if (response.statusCode == 200) {
        return FeedOut.fromJson(response.data as Map<String, dynamic>);
      } else if (response.statusCode == 503) {
         throw Exception('Service Unavailable');
      } else {
        throw Exception('Failed to load feed: ${response.statusCode}');
      }
    } on DioException catch (e) {
      if (e.response?.statusCode == 503) {
         throw Exception('Service Unavailable');
      }
      throw Exception('Network error: ${e.message}');
    } catch (e) {
      throw Exception('Error loading feed: $e');
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
