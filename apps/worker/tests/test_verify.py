from worker.verify import (
    SourceRef,
    determine_verification_type,
    detect_numeric_conflicts,
    is_publish_eligible,
)


def test_one_tier2_not_eligible():
    sources = [SourceRef("a", 2, "Example Gazette")]
    assert is_publish_eligible(sources) is False


def test_two_tier2_eligible():
    sources = [
        SourceRef("a", 2, "Example Gazette"),
        SourceRef("b", 2, "Example Herald"),
    ]
    assert is_publish_eligible(sources) is True
    assert determine_verification_type(sources) == "cross_verified"


def test_one_tier1_not_eligible():
    sources = [SourceRef("wire", 1, "Example Wire")]
    assert is_publish_eligible(sources) is False


def test_conflicting_facts_flagged():
    notes = detect_numeric_conflicts({"hires": [400, 520]})
    assert notes == ["Reports differ on hires"]


def test_single_official_local_source_local_scope():
    """A single official_local source with verified_local_source=True can publish a local-scope card."""
    sources = [SourceRef("pib_local", "official_local", "District Admin Press Release", verified_local_source=True)]
    assert is_publish_eligible(sources, scope="district") is True
    assert is_publish_eligible(sources, scope="local") is True
    assert determine_verification_type(sources, scope="district") == "official_source"


def test_official_local_requires_verified_local_source_flag():
    """DoD: Without verified_local_source=True, official_local single-source exception is inert."""
    unverified_sources = [SourceRef("admin", "official_local", "District Admin", verified_local_source=False)]
    assert is_publish_eligible(unverified_sources, scope="district") is False
    assert determine_verification_type(unverified_sources, scope="district") != "official_source"


def test_district_stories_require_standard_two_sources_by_default():
    """DoD: District stories require standard 2+ sources like everything else until a real local source is vetted."""
    single_source = [SourceRef("src1", 2, "Amar Ujala Delhi", verified_local_source=False)]
    assert is_publish_eligible(single_source, scope="district") is False

    two_sources = [
        SourceRef("src1", 2, "Amar Ujala Delhi", verified_local_source=False),
        SourceRef("src2", 2, "Local Reporter", verified_local_source=False),
    ]
    assert is_publish_eligible(two_sources, scope="district") is True
    assert determine_verification_type(two_sources, scope="district") == "cross_verified"


def test_single_nonofficial_source_local_scope_cannot_publish():
    """DoD: A single non-official source still cannot publish in local-scope."""
    sources = [SourceRef("local_blogger", "2", "Local Gazette")]
    assert is_publish_eligible(sources, scope="district") is False
    assert is_publish_eligible(sources, scope="local") is False


def test_single_official_local_in_national_scope_not_eligible():
    """official_local exception is only for district/local scope."""
    sources = [SourceRef("pib_local", "official_local", "District Admin Press Release")]
    assert is_publish_eligible(sources, scope="national") is False
    assert is_publish_eligible(sources, scope="international") is False


def test_flagged_conflict_verification_type():
    sources = [
        SourceRef("a", 2, "Example Gazette"),
        SourceRef("b", 2, "Example Herald"),
    ]
    assert determine_verification_type(sources, scope="district", flagged_conflict=True) == "flagged_conflict"
