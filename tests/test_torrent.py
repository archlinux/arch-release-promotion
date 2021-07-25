from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from arch_release_promotion import torrent


@patch("arch_release_promotion.torrent.Torrent.create_from")
def test_creat_torrent_file(create_from_mock: Mock) -> None:
    torrent.create_torrent_file(path=Path("foo"), webseeds=["foo"], output=Path("bar"))


@patch("arch_release_promotion.torrent.urlopen")
def test_get_webseeds(urlopen_mock: Mock) -> None:
    artifact_type = "foo"
    mirrorlist_url = "https://foo.bar/mirrorlist"
    version = "0.1.0"
    lines = b"# foo bar baz\n#Server = https://foo.bar/$repo/os/$arch\n"
    urlopen_mock.return_value = MagicMock(read=Mock(return_value=lines))

    assert (
        torrent.get_webseeds(
            artifact_type=artifact_type,
            mirrorlist_url=mirrorlist_url,
            version=version,
        )
        == [f"https://foo.bar/releases/{artifact_type}/{version}/"]
    )
    urlopen_mock.assert_called_once_with(mirrorlist_url)
