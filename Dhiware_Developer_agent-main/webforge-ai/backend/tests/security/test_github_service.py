"""Unit tests for app.services.github_service.parse_github_url — the
SSRF/local-file-read guard for the GitHub import feature. This app has no
authentication, so a permissive clone target (git://, ssh://, file://, or
an arbitrary host) would let a caller make the backend fetch from anywhere
reachable from this machine, not just the intended public GitHub repo.
"""
import pytest

from app.services.github_service import InvalidGitHubUrlError, parse_github_url


@pytest.mark.parametrize(
    "url,expected_owner,expected_repo",
    [
        ("https://github.com/facebook/react", "facebook", "react"),
        ("https://github.com/facebook/react.git", "facebook", "react"),
        ("https://github.com/facebook/react/", "facebook", "react"),
        ("  https://github.com/facebook/react  ", "facebook", "react"),
        ("https://github.com/a/b-c_d.e", "a", "b-c_d.e"),
    ],
)
def test_accepts_valid_public_github_urls(url, expected_owner, expected_repo):
    owner, repo = parse_github_url(url)
    assert owner == expected_owner
    assert repo == expected_repo


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/facebook/react",  # not https
        "git://github.com/facebook/react",
        "ssh://git@github.com/facebook/react.git",
        "git@github.com:facebook/react.git",
        "file:///etc/passwd",
        "file://localhost/etc/passwd",
        "https://evil.com/facebook/react",
        "https://github.com.evil.com/facebook/react",  # subdomain trick
        "https://github.com/facebook",  # missing repo segment
        "https://github.com/",
        "https://github.com",
        "",
        "not a url at all",
        "https://GITHUB.COM/facebook/react",  # case: reject, don't guess-normalize
        "https://github.com/../../../etc/passwd",
        "https://169.254.169.254/facebook/react",  # cloud metadata SSRF target
        "https://github.com/facebook/react/../../evil",
    ],
)
def test_rejects_anything_that_is_not_a_public_github_https_url(url):
    with pytest.raises(InvalidGitHubUrlError):
        parse_github_url(url)
