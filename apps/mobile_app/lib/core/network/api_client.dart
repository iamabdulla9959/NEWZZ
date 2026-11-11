import 'package:dio/dio.dart';
import 'api_config.dart';

class ApiClient {
  static final ApiClient _instance = ApiClient._internal();
  late Dio _dio;

  factory ApiClient() {
    return _instance;
  }

  ApiClient._internal() {
    _dio = Dio(
      BaseOptions(
        baseUrl: ApiConfig.baseUrl,
        // Increased timeouts for Render cold starts
        connectTimeout: const Duration(seconds: 30),
        receiveTimeout: const Duration(seconds: 30),
        responseType: ResponseType.json,
      ),
    );

    // LogInterceptor removed entirely to guarantee no sensitive data leakage
  }

  Dio get dio => _dio;
}
