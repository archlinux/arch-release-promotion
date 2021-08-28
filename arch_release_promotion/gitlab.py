from pathlib import Path
from typing import List, Optional
from urllib import request

import gitlab


class Upstream(gitlab.Gitlab):
    """A class to interact with a gitlab instance

    Upstream is derived from gitlab.Gitlab, but implements a few additional convenience methods such as
    self.select_release(), self.download_release() and self.promote_release().
    """

    def __init__(self, url: str, private_token: Optional[str], name: str):
        """Create an instance of Upstream

        Parameters
        ----------
        url: str
            The URL of the gitlab instance to interact with
        private_token: Optional[str]
            An API token to use to interact with the gitlab instance
        name: str
            The name of the project to interact with
        """

        super().__init__(url=url, private_token=private_token)
        self.name = name
        if "/" in name:
            self.project_name = name.split("/")[-1]

    def select_release(self, max_releases: int = 3) -> Optional[str]:
        """Select one release from a project, that is not yet promoted

        Parameters
        ----------
        max_releases: int
            How many releases to show at maximum

        Returns
        -------
        str
            The tag_name of the selected release
        """

        release_tags = self.get_releases(max_releases=max_releases, promoted=False)

        if release_tags:
            selection_string = "".join([f"{index}) {value}\n" for index, value in enumerate(release_tags)])
            selection = input(f"Select a release for {self.name}:\n{selection_string}")
            return release_tags[int(selection)]
        else:
            print("There are no releases to promote!")
            return None

    def get_releases(self, max_releases: int, promoted: bool = False) -> List[str]:
        """Get a list of releases of a project

        Parameters
        ----------
        max_releases: int
            The maximum amount of releases to list
        promoted: bool
            Whether to only consider promoted releases (defaults to False)

        Returns
        -------
        List[str]
            A list of strings representing release tags of the project
        """

        project = self.projects.get(self.name)

        release_tags: List[str] = []

        for release in project.releases.list():
            if promoted:
                # only select releases that are promoted
                if (
                    any(link.name == "Promotion artifact" for link in release.links.list())
                    and len(release_tags) < max_releases
                ):
                    release_tags += [release.tag_name]
            else:
                # only select releases that are not yet promoted
                if (
                    not any(link.name == "Promotion artifact" for link in release.links.list())
                    and len(release_tags) < max_releases
                ):
                    release_tags += [release.tag_name]

        return release_tags

    def download_release(self, tag_name: str, temp_dir: Path, job_name: str) -> Path:
        """Download the build artifacts of a project's release as a compressed file

        Parameters
        ----------
        tag_name: str
            The tag_name of the release to download
        temp_dir: Path
            The directory into which to download
        job_name: str
            The name of the job that provides the release artifacts

        Returns
        -------
        Path
            The file path of the downloaded compressed file
        """

        project = self.projects.get(self.name)
        artifact_zip = temp_dir / Path(f"{self.project_name}-{tag_name}.zip")
        try:
            print(f"Downloading build artifacts of release '{tag_name}' for '{self.name}'...")
            with open(artifact_zip, "wb") as download:
                project.artifacts(
                    ref_name=tag_name,
                    job=job_name,
                    streamed=True,
                    action=download.write,
                )
            print("Done!")
        except gitlab.exceptions.GitlabGetError:
            print(f"Skipping release {tag_name} as there are no artifacts to download")

        return artifact_zip

    def download_promotion_artifact(self, tag_name: str, temp_dir: Path) -> Path:
        """Download the promotion artifact of a project's release

        Parameters
        ----------
        tag_name: str
            The tag_name of the release to download
        temp_dir: Path
            The directory into which to download

        Returns
        -------
        Path
            The file path of the downloaded file
        """

        project = self.projects.get(self.name)
        artifact_links: List[str] = []

        for release in project.releases.list():
            # only select releases that are promoted
            if release.tag_name == tag_name and any(link.name == "Promotion artifact" for link in release.links.list()):
                artifact_links += [link.url for link in release.links.list() if link.name == "Promotion artifact"]

        if not artifact_links:
            raise RuntimeError(
                f"There is no promotion artifact to download for the release '{tag_name}' of project '{project.name}'."
            )
        if len(artifact_links) > 1:
            raise RuntimeError(
                f"There is more than one promotion artifact to download for the release '{tag_name}' "
                f"of project '{project.name}'. Something is wrong!"
            )

        print(f"Downloading promotion artifact of release '{tag_name}' for '{self.name}'...")
        filename, headers = request.urlretrieve(artifact_links[0], filename=temp_dir / Path("promotion.zip"))
        print("Done!")

        return Path(filename)

    def promote_release(self, tag_name: str, file: str) -> None:
        """Upload a promotion file to the project and add it as a link to a release

        Parameters
        ----------
        tag_name: str
            The tag_name of the project's release to attach a link to
        file: str
            The file path for a file to upload to the project
        """

        project = self.projects.get(self.name)
        print(f"Project '{self.name}': Uploading file {file}...")
        uploaded_file = project.upload(filename="promotion.zip", filepath=file)
        print(f"Project '{self.name}': Linking file {file} to release {tag_name}...")
        for release in project.releases.list():
            if release.tag_name == tag_name:
                release.links.create(
                    {"url": f"{self.url}/{self.name}/{uploaded_file['url']}", "name": "Promotion artifact"}
                )
