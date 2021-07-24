import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List

import orjson
from prometheus_client.parser import text_fd_to_metric_families

from arch_release_promotion.release import Release

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


def read_metrics_file(path: Path, metrics: List[str]) -> Dict[str, Dict[str, str]]:
    """Read a metrics file that contains openmetrics based metrics and return metrics that match the keywords

    Parameters
    ----------
    path: Path
        The path of the file to read
    metrics: List[str]
        A list of metric names to search for in the metrics file

    Returns
    -------
    Dict[str, str]:
        A dictionary representing packages, their respective description and their version
    """

    output: Dict[str, Dict[str, str]] = {}

    with open(path, "r") as file:
        for metric in text_fd_to_metric_families(file):
            if metric.name == "version_info" and metric.samples:
                for sample in metric.samples:
                    if (
                        sample.labels.get("package")
                        and sample.labels.get("description")
                        and sample.labels.get("version")
                        and sample.labels.get("package") in metrics
                    ):
                        output.update(
                            {
                                sample.labels.get("package"): {
                                    "description": sample.labels.get("description"),
                                    "version": sample.labels.get("version"),
                                }
                            }
                        )

    return output
