from pathlib import Path
from sys import exit
from typing import Optional

from arch_release_promotion import (
    argparse,
    config,
    files,
    gitlab,
    release,
    signature,
    torrent,
)


def promote_project_release(project: config.ProjectConfig, release_version: Optional[str] = None) -> None:
    """Promote a project's release

    Parameters
    ----------
    project: config.ProjectConfig
        The ProjectConfig object that describes the project's configuration
    release_version: Optional[str]
        The optional release version to promote. If None is provided, interactive user input is required (defaults to
        None)
    """

    settings = config.Settings()
    upstream = gitlab.Upstream(
        url=settings.GITLAB_URL,
        private_token=settings.PRIVATE_TOKEN,
        name=project.name,
    )
    upstream.auth()

    if not release_version:
        release_version = upstream.select_release()
        if not release_version:
            exit(1)

    artifact_temp_dir = files.create_temp_dir()
    promotion_temp_dir = files.create_temp_dir()

    artifact_zip = upstream.download_release(
        job_name=project.job_name,
        tag_name=release_version,
        temp_dir=artifact_temp_dir,
    )
    files.extract_zip_file_to_parent_dir(path=artifact_zip)

    for release_config in project.releases:
        artifact_output_path = artifact_temp_dir / project.output_dir
        artifact_release_path = artifact_output_path / Path(release_config.name)
        artifact_full_path = artifact_release_path / Path(f"{release_config.name}-{release_version}")
        promotion_base_path = promotion_temp_dir / Path("promotion")
        promotion_release_path = promotion_base_path / Path(release_config.name)
        promotion_full_path = promotion_release_path / Path(f"{release_config.name}-{release_version}")
        promotion_full_path.mkdir(parents=True)
        metrics_file = artifact_output_path / project.metrics_file

        signature.sign_files_in_dir(
            path=artifact_full_path,
            developer=settings.PACKAGER,
            gpgkey=settings.GPGKEY,
            file_extensions=release_config.extensions_to_sign,
        )

        metrics = files.read_metrics_file(
            path=metrics_file,
            version_metrics_names=release_config.version_metrics,
            size_metrics_names=release_config.size_metrics,
            amount_metrics_names=release_config.amount_metrics,
        )
        artifact_release = release.Release(
            name=release_config.name,
            version=release_version,
            files=files.files_in_dir(path=artifact_full_path),
            amount_metrics=metrics[0],
            size_metrics=metrics[1],
            version_metrics=metrics[2],
            torrent_file=torrent.create_torrent_file(
                path=artifact_full_path,
                webseeds=torrent.get_webseeds(
                    artifact_type=release_config.name,
                    mirrorlist_url=settings.MIRRORLIST_URL,
                    version=release_version,
                ),
                output=promotion_release_path / Path(f"{release_config.name}-{release_version}.torrent"),
            )
            if release_config.create_torrent
            else None,
            developer=settings.PACKAGER,
            pgp_public_key=settings.GPGKEY,
        )

        files.copy_signatures(source=artifact_full_path, destination=promotion_full_path)
        files.write_release_info_to_file(
            release=artifact_release,
            path=(promotion_release_path / Path(f"{release_config.name}-{release_version}.json")),
        )
        files.write_zip_file_to_parent_dir(path=promotion_base_path)

        upstream.promote_release(
            tag_name=release_version,
            file=str(promotion_temp_dir / Path("promotion.zip")),
        )

    files.remove_temp_dir(path=artifact_temp_dir)
    files.remove_temp_dir(path=promotion_temp_dir)


def main() -> None:
    args = argparse.ArgParseFactory.promote().parse_args()
    if args.project:
        project = config.Projects().get_project(name=args.project)
        promote_project_release(project=project, release_version=args.release if args.release else None)
    else:
        for project in config.Projects().projects:
            promote_project_release(project=project)
