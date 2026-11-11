import 'package:dio/dio.dart';
import 'api_client.dart';

class ApiHealthResult {
  final bool isConnected;
  final int? statusCode;
  final String statusInfo;
  final bool? isDatabaseReady;
  final String? geocoderProvider;
  final String? failureReason;

  ApiHealthResult({
    required this.isConnected,
    this.statusCode,
    required this.statusInfo,
    this.isDatabaseReady,
    this.geocoderProvider,
    this.failureReason,
  });
}

class ApiHealthService {
  final Dio _dio;

  ApiHealthService() : _dio = ApiClient().dio;

  // Named constructor for testing with mock Dio
  ApiHealthService.withDio(this._dio);

  Future<ApiHealthResult> checkHealth() async {
    try {
      final response = await _dio.get('/health');
      if (response.statusCode == 200) {
        final data = response.data;
        if (data is Map<String, dynamic>) {
          return ApiHealthResult(
            isConnected: true,
            statusCode: response.statusCode,
            statusInfo: data['status']?.toString() ?? 'ok',
          );
        } else {
          return ApiHealthResult(
            isConnected: false,
            statusCode: response.statusCode,
            statusInfo: 'error',
            failureReason: 'Unexpected response format',
          );
        }
      } else {
        return ApiHealthResult(
          isConnected: false,
          statusCode: response.statusCode,
          statusInfo: 'error',
          failureReason: 'Server returned an HTTP error',
        );
      }
    } on DioException catch (e) {
      return _handleDioError(e);
    } catch (e) {
      return ApiHealthResult(
        isConnected: false,
        statusInfo: 'error',
        failureReason: 'Unexpected response format',
      );
    }
  }

  Future<ApiHealthResult> checkReady() async {
    try {
      final response = await _dio.get('/ready');
      if (response.statusCode == 200) {
        final data = response.data;
        if (data is Map<String, dynamic>) {
          return ApiHealthResult(
            isConnected: true,
            statusCode: response.statusCode,
            statusInfo: data['status']?.toString() ?? 'ok',
            isDatabaseReady: data['database'] == 'ok',
            geocoderProvider: data['geocoder_provider']?.toString(),
          );
        } else {
          return ApiHealthResult(
            isConnected: false,
            statusCode: response.statusCode,
            statusInfo: 'error',
            failureReason: 'Unexpected response format',
          );
        }
      } else {
        return ApiHealthResult(
          isConnected: false,
          statusCode: response.statusCode,
          statusInfo: 'error',
          failureReason: 'Server returned an HTTP error',
        );
      }
    } on DioException catch (e) {
      return _handleDioError(e);
    } catch (e) {
      return ApiHealthResult(
        isConnected: false,
        statusInfo: 'error',
        failureReason: 'Unexpected response format',
      );
    }
  }

  ApiHealthResult _handleDioError(DioException e) {
    String reason;
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        reason = 'Connection timed out';
        break;
      case DioExceptionType.badResponse:
        reason = 'Server returned an HTTP error';
        break;
      case DioExceptionType.connectionError:
        reason = 'Connection failed (DNS or Server unreachable)';
        break;
      case DioExceptionType.unknown:
      case DioExceptionType.badCertificate:
      case DioExceptionType.cancel:
        if (e.error is FormatException || (e.message != null && e.message!.contains('FormatException'))) {
          reason = 'Invalid JSON response';
        } else {
          reason = 'Connection unavailable';
        }
        break;
      default:
        reason = 'Connection unavailable';
    }
    return ApiHealthResult(
      isConnected: false,
      statusCode: e.response?.statusCode,
      statusInfo: 'unavailable',
      failureReason: reason,
    );
  }
}
