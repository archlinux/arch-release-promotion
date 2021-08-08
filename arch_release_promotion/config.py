from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import toml
from dotenv import dotenv_values
from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, BaseSettings, Extra, validator
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
    """

    name: str
    job_name: str
    output_dir: Path
    metrics_file: Path
    releases: List[ReleaseConfig]


class Projects(BaseSettings):
    """A pydantic BaseSettings class to describe sets of project settings

    Attributes
    ----------
    projects: List[ProjectConfig]
        A list of project configurations
    """

    projects: List[ProjectConfig]

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
    gpgkey: str
        The PGP key id to use for artifact signatures
    packager: str
        The packager name and mail address to use for artifact signatures
    """

    MIRRORLIST_URL: str = "https://archlinux.org/mirrorlist/?country=all&protocol=http&protocol=https"
    GITLAB_URL: str = "https://gitlab.archlinux.org"
    GPGKEY: str
    PACKAGER: str
    PRIVATE_TOKEN: str

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
    def validate_private_token(cls, private_token: str) -> str:
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

        if len(private_token) < 20:
            raise ValueError("The PRIVATE_TOKEN string has to represent a valid private token (20 chars).")

        return private_token
