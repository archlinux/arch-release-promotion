import shutil
import tempfile
import time
import zipfile
from pathlib import Path
from typing import List, Optional, Tuple

import orjson
from prometheus_client.parser import text_fd_to_metric_families
from pydantic import BaseModel

from arch_release_promotion.config import ProjectConfig, Settings
from arch_release_promotion.gitlab import Upstream
from arch_release_promotion.release import (
    AmountMetric,
    Release,
    SizeMetric,
    VersionMetric,
)

TEMP_DIR_PREFIX = "arp-"


def files_in_dir(path: Path) -> List[str]:
    """Return the files in a directory as a list of strings

    Parameters
    ----------
    path: Path
        The path for which to list files

    Raises
    ------
    RuntimeError
        If the provided path is not a directory

    Returns
    -------
    List[str]
        A list of strings representing the files in a directory
    """

    if not path.is_dir():
        raise RuntimeError(f"The path is not a path: {path}")

    return [child.name for child in path.iterdir()]


def get_version_from_artifact_release_dir(path: Path) -> str:
    """Extrapolate the version of a given release path

    Parameters
    ----------
    path: Path
        The path to a release

    Raises
    ------
    RuntimeError
        If the provided path is not a directory

    Returns
    -------
    str
        The version string for the release
    """

    if not path.is_dir():
        raise RuntimeError(f"The path for the release is not a directory: {path}")

    version = path.name.split("-")[1]
    if len(version) < 1:
        raise RuntimeError(f"The extracted version string '{version}' from path '{path}' is not valid.")

    return version


def create_temp_dir() -> Path:
    """Create a temporary directory

    Returns
    -------
    Path
        The path to the directory
    """

    return Path(tempfile.mkdtemp(prefix=TEMP_DIR_PREFIX))


def remove_temp_dir(path: Path) -> None:
    """Remove a temporary directory recursively

    Parameters
    ----------
    path: Path
        The path to a directory to remove

    Raises
    ------
    RuntimeError
        If the to be removed path is not a directory or if its name does not contain TEMP_DIR_PREFIX
    """

    if not path.is_dir():
        raise RuntimeError(f"The path to remove is not a directory: {path}")

    if TEMP_DIR_PREFIX not in path.name:
        raise RuntimeError(f"Can not remove a temporary directory, that is not created by the same tool: {path}")

    shutil.rmtree(path=path)


def extract_zip_file_to_parent_dir(path: Path) -> None:
    """Extract the contents of a ZIP file to the parent directory of that file

    Parameters
    ----------
    path: Path
        The path to a ZIP file

    Raises
    ------
    RuntimeError
        If the path does not specify a valid zip file
    """

    if not zipfile.is_zipfile(path):
        raise RuntimeError(f"The file is not a ZIP file: {path}")

    with zipfile.ZipFile(file=path, mode="r") as zip_file:
        zip_file.extractall(path=path.parent)


def copy_signatures(source: Path, destination: Path) -> None:
    """Copy any signature files from a source directory to a destination directory

    Parameters
    ----------
    source: Path
        The source directory to copy signature files from
    destination: Path
        The destination directory to copy signature files to

    Raises
    ------
    RuntimeError
        If either source or destination is not a directory
    """

    for path in [source, destination]:
        if not path.is_dir():
            raise RuntimeError("The specified path is not a directory: {path}")

    for file in source.iterdir():
        if file.suffix in [".sig"]:
            shutil.copy(src=file, dst=destination)


def write_release_info_to_file(release: Release, path: Path) -> None:
    """Write a Release instance to a JSON file

    Parameters
    ----------
    release: Release
        A release instance that will be serialized to JSON
    path: Path
        The file to write the JSON string to

    Raises
    ------
    IsADirectoryError:
        If the path is a directory
    OSError:
        If the file path is not writable
    """

    with open(path, "wb") as file:
        file.write(
            orjson.dumps(release.dict(), option=orjson.OPT_INDENT_2 | orjson.OPT_APPEND_NEWLINE | orjson.OPT_SORT_KEYS)
        )


def load_release_from_json_payload(path: Path) -> Release:
    """Read a JSON payload and return it as a Release instance

    Parameters
    ----------
    path: Path
        The path to a file containing a JSON payload

    Returns
    -------
    Release
        A Release instance reflecting the data from the JSON payload
    """

    with open(path, "r") as file:
        return Release(**orjson.loads(file.read()))


def write_zip_file_to_parent_dir(path: Path, name: str = "promotion", format: str = "zip") -> None:
    """Create ZIP file of all contents in a directory and write it to the directory's parent

    Parameters
    ----------
    path: Path
        The path to add to the ZIP file
    name: str
        The name to use for the compressed file (defaults to "promotion")
    format: str
        The compressed file format to use (defaults to "zip")
    """

    known_formats = ["zip", "tar", "gztar", "bztar", "xztar"]
    if len(name) < 1:
        raise RuntimeError("The file name has to be at least one char long, but empty string was provided.")
    if format not in known_formats:
        raise RuntimeError(f"The format must be one of {known_formats}, but {format} is provided.")

    shutil.make_archive(base_name=str(path.parent / Path(name)), format=format, root_dir=path)


def read_metrics_file(
    path: Path,
    version_metrics_names: Optional[List[str]],
    size_metrics_names: Optional[List[str]],
    amount_metrics_names: Optional[List[str]],
) -> Tuple[List[AmountMetric], List[SizeMetric], List[VersionMetric]]:
    """Read a metrics file that contains openmetrics based metrics and return those that match the respective keywords

    Parameters
    ----------
    path: Path
        The path of the file to read
    version_metrics_names: Optional[List[str]]
        A list of metric names to search for in the labels of metric samples of type "info"
    size_metrics_names: Optional[List[str]],
        A list of metric names to search for in the labels of metric samples of type "gauge"
    amount_metrics_names: Optional[List[str]],
        A list of metric names to search for in the labels of metric samples of type "summary"

    Returns
    -------
    Tuple[List[AmountMetric], List[SizeMetric], List[VersionMetric]]:
        A Tuple with lists of AmountMetric, SizeMetric and VersionMetric instances derived from the input file
    """

    amount_metrics: List[AmountMetric] = []
    size_metrics: List[SizeMetric] = []
    version_metrics: List[VersionMetric] = []

    if path.exists():
        with open(path, "r") as file:
            for metric in text_fd_to_metric_families(file):
                for sample in metric.samples:
                    if (
                        version_metrics_names
                        and metric.type == "info"
                        and metric.name == "version_info"
                        and sample.labels.get("name") in version_metrics_names
                        and sample.labels.get("description")
                        and sample.labels.get("version")
                    ):
                        version_metrics += [
                            VersionMetric(
                                name=sample.labels.get("name"),
                                description=sample.labels.get("description"),
                                version=sample.labels.get("version"),
                            )
                        ]
                    if (
                        size_metrics_names
                        and metric.type == "gauge"
                        and metric.name == "artifact_bytes"
                        and sample.labels.get("name") in size_metrics_names
                        and sample.labels.get("description")
                        and sample.value
                    ):
                        size_metrics += [
                            SizeMetric(
                                name=sample.labels.get("name"),
                                description=sample.labels.get("description"),
                                size=sample.value,
                            )
                        ]
                    if (
                        amount_metrics_names
                        and metric.type == "summary"
                        and metric.name == "data_count"
                        and sample.labels.get("name") in amount_metrics_names
                        and sample.labels.get("description")
                        and sample.value
                    ):
                        amount_metrics += [
                            AmountMetric(
                                name=sample.labels.get("name"),
                                description=sample.labels.get("description"),
                                amount=sample.value,
                            )
                        ]
    return (amount_metrics, size_metrics, version_metrics)


def create_dir(path: Path) -> Path:
    """Create a directory

    Parameters
    ----------
    path: Path
        The path for which to create a directory

    Raises
    ------
    RuntimeError
        If the path exists but is not a directory

    Returns
    -------
    Path
        The path representing the existing, absolute directory
    """

    path = path.resolve(strict=False)

    if path.exists() and not path.is_dir():
        raise RuntimeError(f"The provided path is not a directory: {path}")
    else:
        path.mkdir(parents=True, exist_ok=True)

    return path


class ProjectFiles(BaseModel):
    """A pydantic model to operate on a project's files and releases

    Attributes
    ----------
    project_config: ProjectConfig
        A ProjectConfig instance describing the project
    upstream: Upstream
        An Upstream instance used for queries to releases of a project
    promoted_releases: List[str]
        A list of version strings
    """

    project_config: ProjectConfig
    upstream: Upstream
    promoted_releases: List[str]

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, project_config: ProjectConfig, settings: Settings) -> None:
        """A custom constructor to initialize an instance of ProjectFiles

        The names of the configured maximum number of promoted releases is retrieved using an Upstream instance.
        If the project's sync_dir does not exist, it will be created.

        Parameters
        ----------
        project_config: ProjectConfig
            A ProjectConfig instance describing the project
        settings: Settings
            A Settings instance used to initialize an Upstream instance
        """

        upstream = Upstream(
            url=settings.GITLAB_URL,
            private_token=None,
            name=project_config.name,
        )
        promoted_releases = upstream.get_releases(
            max_releases=project_config.sync_config.backlog,  # type: ignore
            promoted=True,
        )
        print(f"Synchronizing release versions for {project_config.name}: " f"{', '.join(promoted_releases)}")

        create_dir(path=project_config.sync_config.directory)  # type: ignore

        super().__init__(
            project_config=project_config,
            upstream=upstream,
            promoted_releases=promoted_releases,
        )

    @classmethod
    def sync(self, project_config: ProjectConfig, settings: Settings) -> None:
        """A factory method to initialize an instance of ProjectFiles and synchronize all of its promoted_releases

        Parameters
        ----------
        project_config: ProjectConfig
            A ProjectConfig instance describing the project
        settings: Settings
            A Settings instance used to initialize an Upstream instance
        """

        change_state: List[bool] = []

        project_files = self(
            project_config=project_config,
            settings=settings,
        )

        for child in project_files.project_config.sync_config.directory.iterdir():  # type: ignore
            if child.name.startswith(".tmp-"):
                print(f"Removing pre-existing temporary directory: {child}")
                shutil.rmtree(child)

        with tempfile.TemporaryDirectory(
            prefix=".tmp-",
            dir=project_files.project_config.sync_config.directory  # type: ignore
            if project_files.project_config.sync_config.temp_in_sync_dir  # type: ignore
            else None,
        ) as temp_dir_base_name:
            for promoted_release in project_files.promoted_releases:
                change_state += [
                    project_files._sync_version(temp_dir_base=Path(temp_dir_base_name), version=promoted_release)
                ]

        change_state += [project_files._set_latest_version_symlink()]
        change_state += [project_files._remove_obsolete_releases()]

        if any(change_state):
            project_files._set_last_update_file_timestamp()

    def _set_last_update_file_timestamp(self) -> None:
        """Write the current seconds since the epoch to a "last update file" if it is configured"""

        if self.project_config.sync_config.last_updated_file:  # type: ignore
            print(f"Updating timestamp in {self.project_config.sync_config.last_updated_file}...")  # type: ignore
            with open(self.project_config.sync_config.last_updated_file, "w") as file:  # type: ignore
                file.write(f"{int(time.time())}")

            print("Done!")

    def _remove_obsolete_releases(self) -> bool:
        """Remove obsolete releases of a project from its sync_dir"""

        state: List[bool] = []
        expected_dirs: List[Path] = []
        expected_files: List[Path] = []

        for release_type in self.project_config.releases:
            release_type_dir = self.project_config.sync_config.directory / Path(release_type.name)  # type: ignore
            print(f"Removing obsolete release files from '{release_type_dir}'...")

            expected_dirs += [release_type_dir / Path("latest")]
            expected_dirs += [
                release_type_dir / Path(f"{release_type.name}-{version}") for version in self.promoted_releases
            ]
            expected_files += [
                release_type_dir / Path(f"{release_type.name}-{version}.json") for version in self.promoted_releases
            ]
            expected_files += [
                release_type_dir / Path(f"{release_type.name}-{version}.torrent") for version in self.promoted_releases
            ]

            for file in release_type_dir.iterdir():
                if file.is_dir() and file not in expected_dirs:
                    print(f"Removing directory '{file}'")
                    shutil.rmtree(path=file)
                    state += [True]
                if file.is_file() and file not in expected_files:
                    print(f"Removing file '{file}'")
                    file.unlink()
                    state += [True]

            print("Done!")

        return any(state)

    def _set_latest_version_symlink(self) -> bool:
        """Set the symlink to the latest version in a project's sync_dir"""

        state: List[bool] = []

        if self.promoted_releases:
            latest_version = sorted(self.promoted_releases)[-1]

            for release_type in self.project_config.releases:
                latest_link = (
                    self.project_config.sync_config.directory / Path(release_type.name) / Path("latest")  # type: ignore
                )
                release_dir = Path(f"{release_type.name}-{latest_version}")
                print(f"Establishing '{latest_version}' as latest release version for '{release_type.name}'...")

                if latest_link.exists():
                    if (latest_link.is_symlink() and latest_link.readlink() != release_dir) or latest_link.is_file():
                        latest_link.unlink()
                    if not latest_link.is_symlink() and latest_link.is_dir():
                        shutil.rmtree(path=latest_link)
                if not latest_link.exists():
                    latest_link.symlink_to(release_dir)
                    state += [True]

            print("Done!")

        return any(state)

    def _sync_version(self, temp_dir_base: Optional[Path], version: str) -> bool:
        """Synchronize a project's (release) version

        Download a project release's promotion artifact and use it to establish whether the release version has been
        synchronized fully to the project's sync_dir.
        Download the project release's build artifact, if the release version is not yet (fully) synchronized and move
        the combined artifacts to the project's sync_dir.

        Parameters
        ----------
        temp_dir_base: Optional[Path]
            The directory to use as base for creating temporary directories in when downloading and moving files
        version: str
            The project's release version

        Returns
        -------
        bool
            True if the synchronization introduced changes in the synchronization directory, False otherwise
        """

        with tempfile.TemporaryDirectory(prefix=TEMP_DIR_PREFIX, dir=temp_dir_base) as promotion_temp_dir_name:
            promotion_temp_dir = Path(promotion_temp_dir_name)
            extract_zip_file_to_parent_dir(
                path=self.upstream.download_promotion_artifact(
                    tag_name=version,
                    temp_dir=promotion_temp_dir,
                )
            )
            if self._project_version_requires_sync(version=version):
                with tempfile.TemporaryDirectory(prefix=TEMP_DIR_PREFIX, dir=temp_dir_base) as build_temp_dir_name:
                    build_temp_dir = Path(build_temp_dir_name)
                    build_artifact = self.upstream.download_release(
                        tag_name=version,
                        temp_dir=build_temp_dir,
                        job_name=self.project_config.job_name,
                    )
                    extract_zip_file_to_parent_dir(path=build_artifact)

                    for release_type in [
                        load_release_from_json_payload(path=json_payload)
                        for json_payload in promotion_temp_dir.glob("*/*.json")
                    ]:
                        self.copy_release_type_promotion_artifacts_to_build_dir(
                            release_type=release_type,
                            source_base=promotion_temp_dir,
                            destination_base=build_temp_dir / self.project_config.output_dir,
                        )

                        self.validate_release_type_files(
                            release_type=release_type,
                            path=build_temp_dir / self.project_config.output_dir,
                        )
                        self.move_release_type_to_sync_dir(
                            release=release_type,
                            source_base=build_temp_dir / self.project_config.output_dir,
                            sync_dir=self.project_config.sync_config.directory,  # type: ignore
                        )

                    return True

            return False

    def _is_release_type_synced(self, name: str, version: str) -> bool:
        """Check whether a release type of a project's release version is synchronized fully already

        Parameters
        ----------
        name: str
            The release name
        version: str
            The release version

        Returns
        -------
        bool
            True if the project's release type in the specified version is fully synchronized, False otherwise
        """

        release_base = self.project_config.sync_config.directory / Path(name)  # type: ignore
        release_json = release_base / Path(f"{name}-{version}.json")
        if not release_json.exists():
            return False

        release = load_release_from_json_payload(path=release_json)

        if release.torrent_file and not (release_base / Path(release.torrent_file)).exists():
            return False

        release_dir = release_base / Path(f"{name}-{version}")
        for file in release.files:
            if not (release_dir / Path(file)).exists():
                return False

        return True

    def _project_version_requires_sync(
        self,
        version: str,
    ) -> bool:
        """Evaluate whether a project's release requires syncing

        Parameters
        ----------
        version: str
            The version of the project's release

        Returns
        -------
        bool
            True if any of the release types of the project are not yet fully synchronized, False otherwise
        """

        release_type_states: List[bool] = []
        for project_release_type in self.project_config.releases:
            if not self._is_release_type_synced(
                name=project_release_type.name,
                version=version,
            ):
                release_type_states += [True]
            else:
                release_type_states += [False]

        return any(release_type_states)

    @classmethod
    def copy_release_type_promotion_artifacts_to_build_dir(
        self,
        release_type: Release,
        source_base: Path,
        destination_base: Path,
    ) -> None:
        """Copy promotion artifacts of a release type to its respective build artifact directory

        Parameters
        ----------
        release_type: Release
            The Release instance describing the files to copy
        source_base: Path
            The base directory in which the promotion artifacts of the release type are located
        destination_base: Path
            The base directory in which the build artifacts of the release type are located
        """

        copy_signatures(
            source=source_base / Path(f"{release_type.name}/{release_type.name}-{release_type.version}"),
            destination=destination_base / Path(f"{release_type.name}/{release_type.name}-{release_type.version}"),
        )
        # move torrent file if it exists
        if release_type.torrent_file:
            (source_base / Path(f"{release_type.name}/{release_type.torrent_file}")).rename(
                destination_base / Path(f"{release_type.name}/{release_type.torrent_file}")
            )
        # move JSON payload
        (source_base / Path(f"{release_type.name}/{release_type.name}-{release_type.version}.json")).rename(
            (destination_base / Path(f"{release_type.name}/{release_type.name}-{release_type.version}.json"))
        )

    @classmethod
    def validate_release_type_files(self, release_type: Release, path: Path) -> None:
        """Validate the files of a release type

        Parameters
        ----------
        release_type: Release
            The Release instance describing the release type
        path: Path
            The directory in which the files for the release type are located

        Raises
        ------
        RuntimeError
            If one of the files is missing
        """

        print(f"Validating release type '{release_type.name}' version '{release_type.version}'...")

        json_payload = Path(f"{release_type.name}/{release_type.name}-{release_type.version}.json")
        if not (path / json_payload).exists():
            raise RuntimeError(f"The file '{json_payload}' does not exist.")

        torrent_file = Path(f"{release_type.name}/{release_type.name}-{release_type.version}.torrent")
        if release_type.torrent_file and not (path / torrent_file).exists():
            raise RuntimeError(f"The file '{torrent_file}' does not exist.")

        for file in release_type.files:
            file_path = Path(f"{release_type.name}/{release_type.name}-{release_type.version}/{file}")
            if not (path / file_path).exists():
                raise RuntimeError(f"The file '{file_path}' does not exist.")

        print("Done!")

    @classmethod
    def move_release_type_to_sync_dir(self, release: Release, source_base: Path, sync_dir: Path) -> None:
        """Move a validated version of a release type to a sync directory

        Parameters
        ----------
        release_type: Release
            The Release instance describing the release type
        source_base: Path
            The directory in which the files for the release type are located
        sync_dir: Path
            The directory to which the release type files are moved
        """

        print(f"Moving release type '{release.name}' version '{release.version}' to '{sync_dir}'...")

        release_type_base = sync_dir / Path(f"{release.name}")
        create_dir(release_type_base)
        destination_release_dir = release_type_base / Path(f"{release.name}-{release.version}")

        # if the destination exists already, remove it first
        if destination_release_dir.exists():
            if destination_release_dir.is_dir():
                shutil.rmtree(path=destination_release_dir)
            else:
                destination_release_dir.unlink()

        destination_release_dir.mkdir(parents=True)

        for file in release.files:
            shutil.move(
                src=source_base / Path(f"{release.name}/{release.name}-{release.version}/{file}"),
                dst=destination_release_dir / Path(f"{file}"),
            )

        if release.torrent_file:
            shutil.move(
                src=source_base / Path(f"{release.name}/{release.name}-{release.version}.torrent"),
                dst=release_type_base / Path(f"{release.name}-{release.version}.torrent"),
            )

        shutil.move(
            src=source_base / Path(f"{release.name}/{release.name}-{release.version}.json"),
            dst=release_type_base / Path(f"{release.name}-{release.version}.json"),
        )

        print("Done!")
