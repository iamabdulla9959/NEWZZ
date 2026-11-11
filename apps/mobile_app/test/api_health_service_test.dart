import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';
import 'package:mockito/annotations.dart';
import 'package:mobile_app/core/network/api_health_service.dart';
import 'api_health_service_test.mocks.dart';

@GenerateMocks([Dio])
void main() {
  late MockDio mockDio;
  late ApiHealthService healthService;

  setUp(() {
    mockDio = MockDio();
    healthService = ApiHealthService.withDio(mockDio);
  });

  group('ApiHealthService Tests', () {
    test('/health returns 200 OK', () async {
      when(mockDio.get('/health')).thenAnswer(
        (_) async => Response(
          requestOptions: RequestOptions(path: '/health'),
          statusCode: 200,
          data: {'status': 'ok'},
        ),
      );

      final result = await healthService.checkHealth();
      expect(result.isConnected, true);
      expect(result.statusCode, 200);
      expect(result.statusInfo, 'ok');
    });

    test('/health returns 503', () async {
      when(mockDio.get('/health')).thenAnswer(
        (_) async => Response(
          requestOptions: RequestOptions(path: '/health'),
          statusCode: 503,
          data: {},
        ),
      );

      final result = await healthService.checkHealth();
      expect(result.isConnected, false);
      expect(result.statusCode, 503);
    });

    test('/ready returns 200 and database is ready', () async {
      when(mockDio.get('/ready')).thenAnswer(
        (_) async => Response(
          requestOptions: RequestOptions(path: '/ready'),
          statusCode: 200,
          data: {'status': 'ok', 'database': 'ok', 'geocoder_provider': 'nominatim'},
        ),
      );

      final result = await healthService.checkReady();
      expect(result.isConnected, true);
      expect(result.isDatabaseReady, true);
      expect(result.geocoderProvider, 'nominatim');
    });

    test('/ready returns 200 but database is NOT ready', () async {
      when(mockDio.get('/ready')).thenAnswer(
        (_) async => Response(
          requestOptions: RequestOptions(path: '/ready'),
          statusCode: 200,
          data: {'status': 'ok', 'database': 'error'},
        ),
      );

      final result = await healthService.checkReady();
      expect(result.isConnected, true);
      expect(result.isDatabaseReady, false);
    });

    test('Connection Timeout handling', () async {
      when(mockDio.get('/health')).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: '/health'),
          type: DioExceptionType.connectionTimeout,
        ),
      );

      final result = await healthService.checkHealth();
      expect(result.isConnected, false);
      expect(result.failureReason, 'Connection timed out');
    });

    test('DNS / Connection Error handling', () async {
      when(mockDio.get('/ready')).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: '/ready'),
          type: DioExceptionType.connectionError,
        ),
      );

      final result = await healthService.checkReady();
      expect(result.isConnected, false);
      expect(result.failureReason, 'Connection failed (DNS or Server unreachable)');
    });

    test('/health returns valid JSON with unexpected structure', () async {
      when(mockDio.get('/health')).thenAnswer(
        (_) async => Response(
          requestOptions: RequestOptions(path: '/health'),
          statusCode: 200,
          data: ['list', 'instead', 'of', 'map'], 
        ),
      );

      final result = await healthService.checkHealth();
      expect(result.isConnected, false);
      expect(result.statusCode, 200);
      expect(result.failureReason, 'Unexpected response format');
    });

    test('/ready returns valid JSON missing fields', () async {
      when(mockDio.get('/ready')).thenAnswer(
        (_) async => Response(
          requestOptions: RequestOptions(path: '/ready'),
          statusCode: 200,
          data: {'other': 'field'},
        ),
      );

      final result = await healthService.checkReady();
      expect(result.isConnected, true);
      expect(result.isDatabaseReady, false);
      expect(result.statusInfo, 'ok');
    });

    test('HTTP error preserves status code', () async {
      when(mockDio.get('/health')).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: '/health'),
          type: DioExceptionType.badResponse,
          response: Response(
            requestOptions: RequestOptions(path: '/health'),
            statusCode: 404,
          ),
        ),
      );

      final result = await healthService.checkHealth();
      expect(result.isConnected, false);
      expect(result.statusCode, 404);
      expect(result.failureReason, 'Server returned an HTTP error');
    });

    test('Malformed JSON mapping error', () async {
      when(mockDio.get('/health')).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: '/health'),
          type: DioExceptionType.unknown,
          error: const FormatException('Unexpected character'),
        ),
      );

      final result = await healthService.checkHealth();
      expect(result.isConnected, false);
      expect(result.failureReason, 'Invalid JSON response');
    });

    test('Network failure without HTTP status', () async {
      when(mockDio.get('/health')).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: '/health'),
          type: DioExceptionType.connectionError,
        ),
      );

      final result = await healthService.checkHealth();
      expect(result.isConnected, false);
      expect(result.statusCode, isNull);
      expect(result.failureReason, 'Connection failed (DNS or Server unreachable)');
    });
  });
}
