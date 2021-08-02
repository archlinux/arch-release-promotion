from typing import List, Optional

from pydantic import BaseModel


class Metric(BaseModel):
    """A pydantic model describing a metric

    Attributes
    ----------
    name: str
        A name for the metric
    description: str
        A description for the metric
    """

    name: str
    description: str


class SizeMetric(Metric):
    """A pydantic model describing a size metric

    Attributes
    ----------
    size: int
    """

    size: int


class AmountMetric(Metric):
    """A pydantic model describing an amount metric

    Attributes
    ----------
    amount: int
    """

    amount: int


class VersionMetric(Metric):
    """A pydantic model describing a version metric

    Attributes
    ----------
    version: str
    """

    version: str


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
    amount_metrics: List[AmountMetric]
        A list of AmountMetric instances that are related to the release
    size_metrics: List[SizeMetric]
        A list of SizeMetric instances that are related to the release
    version_metrics: List[VersionMetric]
        A list of VersionMetric instances that are related to the release
    torrent_file: str
        A string representing the name of a torrent file for the release
    developer: str
        The name and mail address of the developer creating the release
    pgp_public_key: str
        The long format of the PGP public key ID used to sign artifacts in the release
    """

    name: str
    version: str
    files: List[str]
    amount_metrics: List[AmountMetric]
    size_metrics: List[SizeMetric]
    version_metrics: List[VersionMetric]
    torrent_file: Optional[str]
    developer: str
    pgp_public_key: str
