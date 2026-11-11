class ApiConfig {
  /// Base URL of the API.
  /// Defaults to the Render production staging endpoint.
  static const String baseUrl = String.fromEnvironment(
    'NEWZZ_API_BASE_URL',
    defaultValue: 'https://newzz-5e19.onrender.com',
  );
}
