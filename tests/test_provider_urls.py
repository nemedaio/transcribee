"""Tests for URL normalization edge cases."""
import pytest

from transcribee.services.provider_urls import InvalidVideoUrlError, VideoUrlNormalizer


@pytest.fixture
def normalizer():
    return VideoUrlNormalizer()


# --- Invalid URLs ---

def test_rejects_empty_string(normalizer):
    with pytest.raises(InvalidVideoUrlError, match="absolute http"):
        normalizer.normalize("")


def test_rejects_whitespace_only(normalizer):
    with pytest.raises(InvalidVideoUrlError, match="absolute http"):
        normalizer.normalize("   ")


def test_rejects_relative_url(normalizer):
    with pytest.raises(InvalidVideoUrlError, match="absolute http"):
        normalizer.normalize("example.com/video")


def test_rejects_ftp_scheme(normalizer):
    with pytest.raises(InvalidVideoUrlError, match="absolute http"):
        normalizer.normalize("ftp://example.com/video")


def test_rejects_javascript_scheme(normalizer):
    with pytest.raises(InvalidVideoUrlError, match="absolute http"):
        normalizer.normalize("javascript:alert(1)")


def test_rejects_file_scheme(normalizer):
    with pytest.raises(InvalidVideoUrlError, match="absolute http"):
        normalizer.normalize("file:///etc/passwd")


# --- Generic URLs ---

def test_generic_url_preserves_query_params(normalizer):
    result = normalizer.normalize("https://example.com/watch?v=42&t=10")

    assert result.normalized_url == "https://example.com/watch?v=42&t=10"
    assert result.provider == "generic"


def test_generic_url_strips_fragment(normalizer):
    result = normalizer.normalize("https://example.com/watch?v=42#comment")

    assert "#" not in result.normalized_url


def test_generic_url_lowercases_domain(normalizer):
    result = normalizer.normalize("https://EXAMPLE.COM/Video")

    assert result.source_domain == "example.com"


def test_http_scheme_is_accepted(normalizer):
    result = normalizer.normalize("http://example.com/video")

    assert result.normalized_url.startswith("http://")


# --- LinkedIn URLs ---

def test_linkedin_strips_all_tracking_params(normalizer):
    url = "https://www.linkedin.com/feed/update/urn:li:activity:123/?trk=public_post&lipi=abc&utm_source=x"
    result = normalizer.normalize(url)

    assert "trk=" not in result.normalized_url
    assert "lipi=" not in result.normalized_url
    assert "utm_source=" not in result.normalized_url


def test_linkedin_normalizes_country_subdomain(normalizer):
    result = normalizer.normalize("https://es.linkedin.com/feed/update/urn:li:activity:123")

    assert result.source_domain == "www.linkedin.com"
    assert result.normalized_url.startswith("https://www.linkedin.com/")


def test_linkedin_strips_trailing_slash(normalizer):
    result = normalizer.normalize("https://www.linkedin.com/posts/some-post/")

    assert not result.normalized_url.endswith("/")


def test_linkedin_video_url_is_supported(normalizer):
    result = normalizer.normalize("https://www.linkedin.com/video/live/urn:li:ugcPost:123")

    assert result.provider == "linkedin"


def test_linkedin_embed_url_is_supported(normalizer):
    result = normalizer.normalize("https://www.linkedin.com/embed/feed/update/urn:li:share:123")

    assert result.provider == "linkedin"


def test_linkedin_pulse_url_is_supported(normalizer):
    result = normalizer.normalize("https://www.linkedin.com/pulse/some-article-title")

    assert result.provider == "linkedin"


def test_linkedin_rejects_search_page(normalizer):
    with pytest.raises(InvalidVideoUrlError, match="profile or directory"):
        normalizer.normalize("https://www.linkedin.com/search/results/all/?keywords=test")


def test_linkedin_rejects_jobs_page(normalizer):
    with pytest.raises(InvalidVideoUrlError, match="profile or directory"):
        normalizer.normalize("https://www.linkedin.com/jobs/view/123456")


def test_linkedin_rejects_learning_page(normalizer):
    with pytest.raises(InvalidVideoUrlError, match="profile or directory"):
        normalizer.normalize("https://www.linkedin.com/learning/some-course")


def test_linkedin_rejects_unsupported_path(normalizer):
    with pytest.raises(InvalidVideoUrlError, match="supports feed updates"):
        normalizer.normalize("https://www.linkedin.com/messaging/thread/123")


def test_linkedin_company_without_posts_is_rejected(normalizer):
    with pytest.raises(InvalidVideoUrlError, match="supports feed updates"):
        normalizer.normalize("https://www.linkedin.com/company/openai/about/")
