class TextSanitizer {
  /// Strips repeated headline, publisher prefixes, and duplicate opening clauses from the summary.
  static String cleanSummary(String headline, String summary) {
    if (summary.isEmpty) return summary;

    var s = summary.trim();
    final h = headline.trim();

    // 1. Direct prefix match
    if (s.toLowerCase().startsWith(h.toLowerCase())) {
      s = s.substring(h.length).trim();
    } else {
      // Word-level prefix match (tolerant of slight punctuation differences)
      final hWords = h.split(RegExp(r'\s+'));
      final sWords = s.split(RegExp(r'\s+'));

      if (hWords.length >= 3 && sWords.length > hWords.length) {
        bool matches = true;
        for (int i = 0; i < hWords.length && i < sWords.length; i++) {
          final w1 = hWords[i].replaceAll(RegExp(r'[^\w]'), '').toLowerCase();
          final w2 = sWords[i].replaceAll(RegExp(r'[^\w]'), '').toLowerCase();
          if (w1 != w2) {
            matches = false;
            break;
          }
        }
        if (matches) {
          s = sWords.skip(hWords.length).join(' ').trim();
        }
      }
    }

    // 2. Strip leading punctuation, dots, dashes, colons
    s = s.replaceFirst(RegExp(r'^[\.\:\-\–\—\,\s]+'), '').trim();

    // 3. Strip publisher prefixes left at the start
    s = s.replaceFirst(
      RegExp(r'^(NBC News|BBC News|BBC|Reuters|CNN|The Hindu|Times of India|NDTV News|NDTV|Livemint|The Economic Times)\s*[\:\-\–\—\.]*\s*', caseSensitive: false),
      '',
    ).trim();

    // 4. Strip duplicate consecutive sentences
    final sentences = s.split(RegExp(r'(?<=[.!?])\s+'));
    if (sentences.length >= 2) {
      final s1 = sentences[0].replaceAll(RegExp(r'[^\w]'), '').toLowerCase();
      final s2 = sentences[1].replaceAll(RegExp(r'[^\w]'), '').toLowerCase();
      if (s1.isNotEmpty && s1 == s2) {
        s = sentences.skip(1).join(' ').trim();
      }
    }

    // 5. Fallback if summary was stripped empty or too short
    if (s.length < 15) {
      return 'Read the verified journalistic reporting and full timeline developments in the dossier below.';
    }

    // 6. Ensure first letter is capitalized
    return s[0].toUpperCase() + s.substring(1);
  }
}
