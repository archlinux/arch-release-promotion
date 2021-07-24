from typing import Dict, List, Optional

from pydantic import BaseModel


class Release(BaseModel):
    """A pydantic model describing a release

    Attributes
    ----------
    name: str
        The name of the artifact type
    version: str
        The version of the artifact
    files: List[str]
        A list of files that belong to the release
    info: Dict[str, str]
        A dictionary that provides additional information about the release
    developer: str
        The name and mail address of the developer creating the release
    pgp_public_key: str
        The long format of the PGP public key ID used to sign artifacts in the release
    """

    name: str
    version: str
    files: List[str]
    info: Optional[Dict[str, Dict[str, str]]]
    torrent_file: str
    developer: str
    pgp_public_key: str
