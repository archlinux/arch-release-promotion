from pathlib import Path
from typing import List
from urllib.request import urlopen

from torrentool.api import Torrent


def create_torrent_file(path: Path, webseeds: List[str], output: Path) -> str:
    """Create a torrent file for a path and write it to an output directory

    Parameters
    ----------
    path: Path
        The path for which to create a torrent file
    webseeds: List[str]
        The list of webseeds to add to the torrent file
    output: Path
        A path to write the .torrent file to

    Returns
    -------
    str
        A string representing the name of the torrent file
    """

    torrent = Torrent.create_from(path)
    torrent.webseeds = webseeds
    torrent.to_file(output)

    return output.name


def get_webseeds(
    artifact_type: str,
    mirrorlist_url: str,
    version: str,
) -> List[str]:
    """Read available mirrors from a remote URL and return them in a formatted list representing the webseeds for a
    given artifact type

    Parameters
    ----------
    artifact_type: str
        The artifact type to create the webseeds for
    mirrorlist_url: str
        A URL used to retrieve the list of mirrors
    version: str
        The version of the artifact type to create the webseeds for

    Returns
    -------
    List[str]
        A list of strings representing webseeds for an artifact type in a specific version
    """

    webseeds: List[str] = []
    url = urlopen(mirrorlist_url)
    for line in url.read().decode("utf-8").split("\n"):
        if "#Server = " in line:
            webseeds += [
                line.replace("#Server = ", "",).replace(
                    "$repo/os/$arch",
                    f"releases/{artifact_type}/{version}/",
                )
            ]

    return webseeds
