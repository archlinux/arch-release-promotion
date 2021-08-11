from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import toml
from dotenv import dotenv_values
from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, BaseSettings, Extra, root_validator, validator
from pydantic.env_settings import SettingsSourceCallable
from xdg.BaseDirectory import xdg_config_home

MAKEPKG_CONFIGS = [
    Path("/etc/makepkg.conf"),
    Path(f"{xdg_config_home}/pacman/makepkg.conf"),
    Path("~/.makepkg.conf"),
]

PROJECTS_CONFIGS = [
    Path("/etc/arch-release-promotion/projects.toml"),
    Path(f"{xdg_config_home}/arch-release-promotion/projects.toml"),
]

PROJECTS_SYNC_DIR = Path("/var/lib/arch-release-promotion/")
PROJECTS_SYNC_BACKLOG = 3


class ReleaseConfig(BaseModel):
    """A pydantic model describing the configuration of a project's release

    Attributes
    ----------
    name: str
        The name of the release (type)
    version_metrics: Optional[List[str]]
        A list of names that identify labels in metric samples of type "info", that should be extracted from the
        project's metrics file
    size_metrics: Optional[List[str]]
        A list of names that identify labels in metric samples of type "gauge", that should be extracted from the
        project's metrics file
    amount_metrics: Optional[List[str]]
        A list of names that identify labels in metric samples of type "summary", that should be extracted from the
        project's metrics file
    extensions_to_sign: List[str]
        A list of file extensions for which to create detached signatures
    create_torrent: bool
        A bool indicating whether to create a torrent file for the release (defaults to False)
    """

    name: str
    version_metrics: Optional[List[str]]
    size_metrics: Optional[List[str]]
    amount_metrics: Optional[List[str]]
    extensions_to_sign: List[str]
    create_torrent: bool = False


class SyncConfig(BaseModel):
    """A pydantic model describing configuration for synchronization

    Attributes
    ----------
    backlog: int
        The backlog of releases to retain at a maximum (defaults to PROJECTS_SYNC_BACKLOG when a SysConfig instance is
        used in a Projects instance or a ProjectConfig instance).
    directory: Path
        A directory into which to sync project release types and their respective releases (defaults to
        PROJECTS_SYNC_DIR when a SysConfig instance is used in a Projects instance or a ProjectConfig instance).
    last_updated_file: Optional[Path]
        The optional path to a file, that is used to write a timestamp to, if the synchronization of a project leads to
        the changing of data on disk (defaults to None).
    temp_in_sync_dir: bool
        A bool specifying whether to download temporary data to temporary directories below sync_dir (defaults to True).
        If False is specified the temporary data is downloaded to the respective user's temporary directory.
    """

    backlog: Optional[int]
    directory: Optional[Path]
    last_updated_file: Optional[Path] = None
    temp_in_sync_dir: bool = True


class ProjectConfig(BaseModel):
    """A pydantic model describing the configuration of a project

    Attributes
    ----------
    name: str
        The name of the project
    job_name: str
        The project's job, that offers release artifacts
    output_dir: Path
        The project's configured output directory for release artifacts
    metrics_file: Path
        The project's metrics file
    releases: List[ReleaseConfig]
        The project's list of releases
    sync_config: Optional[SyncConfig]
        An optional SyncConfig instance, which is used to override any global defaults.
    """

    name: str
    job_name: str
    output_dir: Path
    metrics_file: Path
    releases: List[ReleaseConfig]
    sync_config: Optional[SyncConfig]


class Projects(BaseSettings):
    """A pydantic BaseSettings class to describe sets of project settings

    Attributes
    ----------
    projects: List[ProjectConfig]
        A list of project configurations
    sync_config: Optional[SyncConfig]
        An optional SyncConfig instance, which is used to override any implicit defaults and sets defaults for all
        ProjectConfig instances in projects.
    """

    projects: List[ProjectConfig]
    sync_config: Optional[SyncConfig]

    class Config:

        extra = Extra.ignore

        @classmethod
        def customise_sources(
            cls,
            init_settings: SettingsSourceCallable,
            env_settings: SettingsSourceCallable,
            file_secret_settings: SettingsSourceCallable,
        ) -> Tuple[SettingsSourceCallable, ...]:
            return (read_projects_conf,)

    @validator("projects")
    def validate_project_releases_unique(cls, projects: List[ProjectConfig]) -> List[ProjectConfig]:
        """Validate the list of ProjectConfig instances to only contain uniquely named ReleaseConfig instances

        Parameters
        ----------
        projects: List[ProjectConfig]
            A list of ProjectConfig instances

        Raises
        ------
        ValueError
            If a non-unique name is encountered among any ReleaseConfig instance

        Returns
        -------
        List[ProjectConfig]
            The unmodified list of ProjectConfig instances
        """

        release_types: List[ReleaseConfig] = []
        for project in projects:
            release_types += project.releases
        names = [release_type.name for release_type in release_types]

        if len(set(names)) < len(names):
            duplicates = [name for name, count in Counter(names).items() if count > 1]
            raise ValueError(
                f"The following release type {'name' if len(duplicates) == 1 else 'names'} "
                f"{'is' if len(duplicates) == 1 else 'are'} not unique: "
                f"{duplicates[0] if len(duplicates) == 1 else duplicates}"
            )

        return projects

    @root_validator
    def validate_projects(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the list of ProjectConfig instances and override defaults

        If a ProjectConfig does not specify a SysConfig, override it with the global SysConfig. If a global SysConfig
        does not exist, override with an implicit default where directory defaults to PROJECTS_SYNC_DIR and backlog to
        PROJECTS_SYNC_BACKLOG.

        Parameters
        ----------
        values: Dict[str, Any]
            A dict with all values of the Projects instance

        Returns
        -------
        values: Dict[str, Any]
            The (potentially modified) dict with all values of the Projects instance
        """

        default_sync_config = SyncConfig(
            directory=PROJECTS_SYNC_DIR,
            backlog=PROJECTS_SYNC_BACKLOG,
            last_updated_file=None,
        )

        projects: List[ProjectConfig] = values.get("projects")  # type: ignore
        sync_config: Optional[SyncConfig] = values.get("sync_config")

        # merge global sync_config with defaults
        if sync_config:
            global_sync_config = SyncConfig(
                directory=sync_config.directory or default_sync_config.directory,
                backlog=sync_config.backlog or default_sync_config.backlog,
                last_updated_file=sync_config.last_updated_file or default_sync_config.last_updated_file,
                temp_in_sync_dir=False if not sync_config.temp_in_sync_dir else default_sync_config.temp_in_sync_dir,
            )
        else:
            global_sync_config = default_sync_config

        for project in projects:
            if not project.sync_config:
                project.sync_config = global_sync_config
            else:
                project.sync_config = SyncConfig(
                    directory=project.sync_config.directory or global_sync_config.directory,
                    backlog=project.sync_config.backlog or global_sync_config.backlog,
                    last_updated_file=project.sync_config.last_updated_file or global_sync_config.last_updated_file,
                    temp_in_sync_dir=False
                    if not project.sync_config.temp_in_sync_dir
                    else global_sync_config.temp_in_sync_dir,
                )

        values["projects"] = projects

        return values

    def get_project(self, name: str) -> ProjectConfig:
        """Return a ProjectConfig by name

        Parameters
        ----------
        name: str
            A string that matches the name attribute of a ProjectConfig

        Raises
        ------
        RuntimeError
            If no ProjectConfig instance of the given name can be found

        Returns
        -------
        ProjectConfig
            The configuration identified by the provided name
        """

        for project in self.projects:
            if project.name == name:
                return project

        raise RuntimeError(f"No project configuration of the name '{name}' can be found!")


def read_projects_conf(settings: BaseSettings) -> Dict[str, Any]:
    """Read all available projects.toml files"""

    config: Dict[str, Any] = {}
    config_files: List[str] = []
    for config_file in PROJECTS_CONFIGS:
        if config_file.exists():
            config_files += [str(config_file)]

    if config_files:
        config.update(toml.load(config_files))
    else:
        raise RuntimeError("There are no project configuration files!")

    return config


def read_makepkg_conf(settings: BaseSettings) -> Dict[str, Any]:
    """Read all available makepkg.conf files"""

    config: Dict[str, Optional[str]] = {}
    for config_file in MAKEPKG_CONFIGS:
        config.update(dotenv_values(config_file.expanduser()))

    return config


class Settings(BaseSettings):
    """A class to describe configuration

    Attributes
    ----------
    GITLAB_URL: str
        A URL for a GitLab upstream (defaults to "https://gitlab.archlinux.org")
    GPGKEY: str
        The PGP key id to use for artifact signatures
    MIRRORLIST_URL: str
        A URL to derive a mirrorlist from (defaults to
        "https://archlinux.org/mirrorlist/?country=all&protocol=http&protocol=https")
    PACKAGER: str
        The packager name and mail address (UID) to use for artifact signatures
    PRIVATE_TOKEN: Optional[str]
        An optional private token to use for authenticating against an upstream
    """

    GITLAB_URL: str = "https://gitlab.archlinux.org"
    GPGKEY: str
    MIRRORLIST_URL: str = "https://archlinux.org/mirrorlist/?country=all&protocol=http&protocol=https"
    PACKAGER: str
    PRIVATE_TOKEN: Optional[str]

    class Config:

        extra = Extra.ignore

        @classmethod
        def customise_sources(
            cls,
            init_settings: SettingsSourceCallable,
            env_settings: SettingsSourceCallable,
            file_secret_settings: SettingsSourceCallable,
        ) -> Tuple[SettingsSourceCallable, ...]:
            return (
                read_makepkg_conf,
                env_settings,
            )

    @validator("PACKAGER")
    def validate_packager(cls, packager: str) -> str:
        """A validator for the PACKAGER attribute

        Parameters
        ----------
        packager: str
            The packager string to validate

        Raises
        ------
        ValueError
            If the packager string is not valid

        Returns
        -------
        str
            A valid packager string
        """

        if len(packager) == 0:
            raise ValueError("The PACKAGER string can not be empty.")
        if not ("<" in packager and ">" in packager):
            raise ValueError(f"The PACKAGER string has to define a mail address: {packager}")
        split_packager = packager.replace(">", "").split("<")
        if len(split_packager[0]) < 1:
            raise ValueError(f"The PACKAGER string has to define a name: {packager}")
        try:
            validate_email(split_packager[1])
        except EmailNotValidError as e:
            raise ValueError(f"The PACKAGER string has to define a valid mail address: {packager}\n{e}")

        return packager

    @validator("GPGKEY")
    def validate_gpgkey(cls, gpgkey: str) -> str:
        """A validator for the GPGKEY attribute

        Parameters
        ----------
        gpgkey: str
            The packager string to validate

        Raises
        ------
        ValueError
            If the gpgkey string is not valid

        Returns
        -------
        str
            A gpgkey string in long-format
        """

        if len(gpgkey) < 40:
            raise ValueError(f"The GPGKEY string has to represent a PGP key ID in long format (40 chars): {gpgkey}")

        return gpgkey

    @validator("PRIVATE_TOKEN")
    def validate_private_token(cls, private_token: Optional[str]) -> Optional[str]:
        """A validator for the PRIVATE_TOKEN attribute

        Parameters
        ----------
        private_token: str
            The private token string to validate

        Raises
        ------
        ValueError
            If the private token string is not valid

        Returns
        -------
        str
            A gpgkey string in long-format
        """

        if private_token is None:
            return None

        if len(private_token) < 20:
            raise ValueError("The PRIVATE_TOKEN string has to represent a valid private token (20 chars).")

        return private_token
