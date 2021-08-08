from pathlib import Path
from typing import List, Optional

import gitlab


class Upstream(gitlab.Gitlab):
    """A class to interact with a gitlab instance

    Upstream is derived from gitlab.Gitlab, but implements a few additional convenience methods such as
    self.select_release(), self.download_release() and self.promote_release().
    """

    def __init__(self, url: str, private_token: str, name: str):
        """Create an instance of Upstream

        Parameters
        ----------
        url: str
            The URL of the gitlab instance to interact with
        private_token: str
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

        project = self.projects.get(self.name)

        release_tags: List[str] = []

        for release in project.releases.list():
            # only select releases that are not yet promoted
            if (
                not any(link.name == "Promotion artifact" for link in release.links.list())
                and len(release_tags) < max_releases
            ):
                release_tags += [release.tag_name]

        if release_tags:
            selection_string = "".join([f"{index}) {value}\n" for index, value in enumerate(release_tags)])
            selection = input(f"Select a release for {self.name}:\n{selection_string}")
            return release_tags[int(selection)]
        else:
            print("There are no releases to promote!")
            return None

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
            print(f"Downloading build artifacts of release {tag_name}...")
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
