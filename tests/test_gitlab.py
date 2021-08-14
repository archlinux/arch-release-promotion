from contextlib import nullcontext as does_not_raise
from pathlib import Path
from typing import ContextManager, Optional
from unittest.mock import Mock, patch

from gitlab.exceptions import GitlabGetError
from pytest import mark, raises

from arch_release_promotion import gitlab


@mark.parametrize(
    "name",
    [
        ("foo/test"),
        ("foo"),
    ],
)
def test_gitlab(name: str) -> None:
    assert gitlab.Upstream(
        url="https://foo.bar-mc.foo",
        private_token="THISISAFAKETOKEN",
        name=name,
    )


@mark.parametrize(
    "releases_available, tag_name, link_name, output",
    [
        (True, "0.1.0", "Build artifacts", "0.1.0"),
        (False, "0.1.0", "Build artifacts", None),
        (True, "0.1.0", "Promotion artifact", None),
        (False, "0.1.0", "Promotion artifact", None),
    ],
)
@patch("builtins.input", return_value=0)
def test_gitlab_select_release(
    input_mock: Mock,
    releases_available: bool,
    tag_name: str,
    link_name: str,
    output: Optional[str],
) -> None:
    upstream = gitlab.Upstream(
        url="https://foo.bar-mc.foo",
        private_token="THISISAFAKETOKEN",
        name="foo/bar",
    )

    link = Mock()
    link.name = link_name
    links = Mock()
    links.list.return_value = [link]

    release = Mock()
    release.links = links
    release.tag_name = tag_name

    releases = Mock()
    releases.list.return_value = [release] if releases_available else []

    project = Mock()
    project.releases = releases

    projects = Mock()
    projects.get.return_value = project
    upstream.projects = projects
    assert upstream.select_release() == output


@mark.parametrize(
    "releases_available, tag_name, link_name, max_releases, promoted, output",
    [
        (True, "0.1.0", "Build artifacts", 1, False, ["0.1.0"]),
        (False, "0.1.0", "Build artifacts", 1, False, []),
        (True, "0.1.0", "Promotion artifact", 1, False, []),
        (False, "0.1.0", "Promotion artifact", 1, False, []),
        (True, "0.1.0", "Promotion artifact", 1, True, ["0.1.0"]),
        (True, "0.1.0", "Build artifacts", 1, True, []),
    ],
)
def test_gitlab_get_releases(
    releases_available: bool,
    tag_name: str,
    link_name: str,
    max_releases: bool,
    promoted: bool,
    output: Optional[str],
) -> None:
    upstream = gitlab.Upstream(
        url="https://foo.bar-mc.foo",
        private_token="THISISAFAKETOKEN",
        name="foo/bar",
    )
    link = Mock()
    link.name = link_name
    links = Mock()
    links.list.return_value = [link]

    release = Mock()
    release.links = links
    release.tag_name = tag_name

    releases = Mock()
    releases.list.return_value = [release] if releases_available else []

    project = Mock()
    project.releases = releases

    projects = Mock()
    projects.get.return_value = project
    upstream.projects = projects
    assert upstream.get_releases(max_releases=max_releases, promoted=promoted) == output


def test_gitlab_download_release() -> None:
    upstream = gitlab.Upstream(
        url="https://foo.bar-mc.foo",
        private_token="THISISAFAKETOKEN",
        name="foo/bar",
    )
    upstream.projects = Mock(return_value=Mock())
    upstream.download_release(tag_name="0.1.0", temp_dir=Path("/tmp"), job_name="job")

    project = Mock()
    project.artifacts = Mock(side_effect=GitlabGetError)
    projects = Mock()
    projects.get.return_value = project
    upstream.projects = projects
    upstream.download_release(tag_name="0.1.0", temp_dir=Path("/tmp"), job_name="job")


@mark.parametrize(
    "releases_available, tag_name, multi_promotion, has_link, link_name, link_url, expectation",
    [
        (True, "0.1.0", False, True, "Promotion artifact", "https://foo.bar/download/this/file.zip", does_not_raise()),
        (True, "0.1.0", False, True, "Foo artifact", "https://foo.bar/download/this/file.zip", raises(RuntimeError)),
        (
            False,
            "0.1.0",
            False,
            True,
            "Promotion artifact",
            "https://foo.bar/download/this/file.zip",
            raises(RuntimeError),
        ),
        (
            True,
            "0.1.0",
            True,
            True,
            "Promotion artifact",
            "https://foo.bar/download/this/file.zip",
            raises(RuntimeError),
        ),
    ],
)
@patch("arch_release_promotion.gitlab.request.urlretrieve")
def test_gitlab_download_promotion_artifact(
    urlretrieve_mock: Mock,
    releases_available: bool,
    tag_name: str,
    multi_promotion: bool,
    has_link: bool,
    link_name: str,
    link_url: str,
    expectation: ContextManager[str],
) -> None:
    urlretrieve_mock.return_value = ("foo", None)
    upstream = gitlab.Upstream(
        url="https://foo.bar-mc.foo",
        private_token="THISISAFAKETOKEN",
        name="foo/bar",
    )
    link = Mock()
    link.name = link_name
    link.url = link_url
    links = Mock()
    links.list.return_value = [link]

    release = Mock()
    release.links = links
    release.tag_name = tag_name

    releases = Mock()
    releases.list.return_value = [release] if releases_available else []
    if releases_available and multi_promotion:
        releases.list.return_value = [release, release]

    project = Mock()
    project.releases = releases

    projects = Mock()
    projects.get.return_value = project
    upstream.projects = projects

    with expectation:
        upstream.download_promotion_artifact(tag_name="0.1.0", temp_dir=Path("/tmp"))
        urlretrieve_mock.assert_called_once_with(link_url, filename=Path("/tmp") / Path("promotion.zip"))


@mark.parametrize("same_tag_name", [(True), (False)])
def test_gitlab_promote_release(same_tag_name: bool) -> None:
    upstream = gitlab.Upstream(
        url="https://foo.bar-mc.foo",
        private_token="THISISAFAKETOKEN",
        name="foo/bar",
    )

    release = Mock()
    release.tag_name = "0.1.0" if same_tag_name else "0.2.0"
    releases = Mock()
    releases.list.return_value = [release]

    project = Mock()
    project.upload.return_value = {"url": "uploaded"}
    project.releases = releases

    projects = Mock()
    projects.get.return_value = project
    upstream.projects = projects
    upstream.promote_release(tag_name="0.1.0", file="file")
