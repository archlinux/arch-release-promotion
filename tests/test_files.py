import tempfile
import zipfile
from contextlib import nullcontext as does_not_raise
from pathlib import Path
from typing import ContextManager, Iterator, List
from unittest.mock import Mock, call, patch

from pytest import fixture, mark, raises

from arch_release_promotion import config, files, release


@fixture
def create_temp_zipfile() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as temp_dir:
        with tempfile.NamedTemporaryFile(dir=temp_dir) as temp_file:
            temp_file.write(b"foobar")
            with zipfile.ZipFile(f"{temp_dir}/compressed.zip", "w") as zip_file:
                zip_file.write(temp_file.name)

        yield Path(str(zip_file.filename))


@fixture
def create_temp_dir() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@fixture
def create_temp_file() -> Iterator[Path]:
    with tempfile.NamedTemporaryFile() as temp_file:
        yield Path(temp_file.name)


@fixture
def create_temp_dir_with_files() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as temp_dir:
        with tempfile.TemporaryDirectory(dir=temp_dir) as inner_temp_dir:
            with tempfile.NamedTemporaryFile(dir=inner_temp_dir, delete=False) as temp_file:
                temp_file.write(b"foobar")
            yield Path(inner_temp_dir)


@fixture
def create_temp_metrics_file() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as temp_dir:
        with tempfile.NamedTemporaryFile(dir=temp_dir, delete=False) as temp_file:
            temp_file.write(b"# TYPE version_info info\n")
            temp_file.write(b"# HELP version_info Package description and version information\n")
            temp_file.write(b'version_info{name="foo", description="Version of foo", version="1.0.0-1"} 1\n')
            temp_file.write(b'version_info{name="bar", not_description="Version of bar", version="1.0.0-1"} 1\n')
            temp_file.write(b"version_info 1\n")
            temp_file.write(b'version{name="foo", description="Version of foo", version="1.0.0-1"} 1\n')
            temp_file.write(b"# TYPE artifact_bytes gauge\n")
            temp_file.write(b"# HELP artifact_bytes Artifact sizes in bytes\n")
            temp_file.write(b'artifact_bytes{name="foo",description="Size of ISO image in MiB"} 832\n')
            temp_file.write(b'artifact_bytes{not_name="foo",description="Size of ISO image in MiB"} 832\n')
            temp_file.write(b"# TYPE data_count summary\n")
            temp_file.write(b"# HELP data_count The amount of packages used in specific buildmodes\n")
            temp_file.write(b'data_count{name="foo",description="The amount of packages in foo"} 369\n')
            temp_file.write(b'data_count{not_name="netboot",description="something else"} 369\n')
        yield Path(temp_file.name)


@fixture
def project_config() -> Iterator[config.ProjectConfig]:
    yield config.ProjectConfig(
        name="foo",
        job_name="bar",
        output_dir="out",
        metrics_file="metrics.txt",
        releases=[],
        sync_config=config.SyncConfig(),
    )


@fixture
def project_files(project_config: config.ProjectConfig) -> Iterator[files.ProjectFiles]:
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch("arch_release_promotion.files.Upstream.get_releases") as get_releases_mock:
            settings_mock = Mock()
            sync_dir = Path(temp_dir) / Path("foo")
            settings_mock.GITLAB_URL = "https://foo.bar"
            get_releases_mock.return_value = ["1.0.0", "1.0.1", "1.0.2"]

            project_config.sync_config.directory = sync_dir  # type: ignore
            yield files.ProjectFiles(
                project_config=project_config,
                settings=settings_mock,
            )


@mark.parametrize(
    "use_dir, expectation",
    [
        (True, does_not_raise()),
        (False, raises(RuntimeError)),
    ],
)
def test_files_in_dir(use_dir: bool, expectation: ContextManager[str]) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        tmp_file = tempfile.NamedTemporaryFile(suffix=".foo", dir=temp_dir, delete=False)
        with expectation:
            assert files.files_in_dir(path=Path(temp_dir) if use_dir else Path(tmp_file.name)) == [
                Path(tmp_file.name).name
            ]


@mark.parametrize(
    "use_dir, version, expectation",
    [
        (True, "0.1.0", does_not_raise()),
        (False, "0.1.0", raises(RuntimeError)),
        (True, "", raises(RuntimeError)),
    ],
)
def test_get_version_from_artifact_release_dir(use_dir: bool, version: str, expectation: ContextManager[str]) -> None:
    with tempfile.TemporaryDirectory(suffix=f"-{version}") as temp_dir:
        tmp_file = tempfile.NamedTemporaryFile(suffix=".foo", dir=temp_dir, delete=False)
        with expectation:
            assert (
                files.get_version_from_artifact_release_dir(path=Path(temp_dir) if use_dir else Path(tmp_file.name))
                == version
            )


def test_create_and_remove_temp_dir() -> None:
    temp_dir = files.create_temp_dir()
    assert isinstance(temp_dir, Path)
    with raises(RuntimeError):
        files.remove_temp_dir(Path("foo"))
    with raises(RuntimeError):
        files.remove_temp_dir(Path("/tmp"))

    with does_not_raise():
        files.remove_temp_dir(temp_dir)


def test_extract_zip_file(create_temp_zipfile: Path) -> None:
    with raises(RuntimeError):
        files.extract_zip_file_to_parent_dir(path=Path("foo"))
    with does_not_raise():
        files.extract_zip_file_to_parent_dir(path=create_temp_zipfile)


@mark.parametrize(
    "create_src, create_dst, expectation",
    [
        (True, True, does_not_raise()),
        (False, True, raises(RuntimeError)),
        (True, False, raises(RuntimeError)),
    ],
)
def test_copy_signatures(
    create_src: bool,
    create_dst: bool,
    expectation: ContextManager[str],
) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        src_dir = temp_dir / Path("source")
        dst_dir = temp_dir / Path("destination")
        if create_src:
            src_dir.mkdir()
            tempfile.NamedTemporaryFile(suffix=".sig", dir=src_dir, delete=False)
            tempfile.NamedTemporaryFile(suffix=".foo", dir=src_dir, delete=False)
        if create_dst:
            dst_dir.mkdir()

        with expectation:
            files.copy_signatures(source=src_dir, destination=dst_dir)


def test_write_release_info_to_file(create_temp_dir: Path) -> None:
    files.write_release_info_to_file(
        release=release.Release(
            name="foo",
            version="1.0.0",
            files=["foo", "bar", "baz"],
            amount_metrics=[],
            size_metrics=[],
            version_metrics=[],
            developer="Foobar McFoo",
            torrent_file="foo-0.1.0.torrent",
            pgp_public_key="SOMEONESKEY",
        ),
        path=(create_temp_dir / Path("foo.json")),
    )

    with raises(IsADirectoryError):
        files.write_release_info_to_file(
            release=release.Release(
                name="foo",
                version="1.0.0",
                files=["foo", "bar", "baz"],
                amount_metrics=[],
                size_metrics=[],
                version_metrics=[],
                developer="Foobar McFoo",
                torrent_file="foo-0.1.0.torrent",
                pgp_public_key="SOMEONESKEY",
            ),
            path=create_temp_dir,
        )


def test_load_release_from_json_payload(create_temp_dir: Path) -> None:
    file_path = create_temp_dir / Path("foo.json")
    release_type = release.Release(
        name="foo",
        version="1.0.0",
        files=["foo", "bar", "baz"],
        amount_metrics=[],
        size_metrics=[],
        version_metrics=[],
        developer="Foobar McFoo",
        torrent_file="foo-0.1.0.torrent",
        pgp_public_key="SOMEONESKEY",
    )
    files.write_release_info_to_file(
        release=release_type,
        path=file_path,
    )
    assert files.load_release_from_json_payload(path=file_path) == release_type


@mark.parametrize(
    "name, format, expectation",
    [
        ("promotion", "zip", does_not_raise()),
        ("", "zip", raises(RuntimeError)),
        ("promotion", "foo", raises(RuntimeError)),
    ],
)
def test_write_zip_file_to_parent_dir(
    create_temp_dir_with_files: Path,
    name: str,
    format: str,
    expectation: ContextManager[str],
) -> None:
    with expectation:
        files.write_zip_file_to_parent_dir(
            path=create_temp_dir_with_files,
            name=name,
            format=format,
        )
        assert (create_temp_dir_with_files.parent / Path(f"{name}.zip")).is_file()


@mark.parametrize(
    "file_exists, version_metrics_names, size_metrics_names, amount_metrics_names",
    [
        (True, [], [], []),
        (False, [], [], []),
        (True, ["foo"], ["foo"], ["foo"]),
        (True, ["bar"], ["foo"], ["foo"]),
        (True, ["bar"], ["foo"], ["bar"]),
        (True, ["bar"], ["bar"], ["foo"]),
    ],
)
def test_read_metrics_file(
    file_exists: bool,
    version_metrics_names: List[str],
    size_metrics_names: List[str],
    amount_metrics_names: List[str],
    create_temp_metrics_file: Path,
) -> None:
    metrics = files.read_metrics_file(
        path=create_temp_metrics_file if file_exists else Path("foo"),
        version_metrics_names=version_metrics_names,
        size_metrics_names=size_metrics_names,
        amount_metrics_names=amount_metrics_names,
    )
    if version_metrics_names == "foo":
        assert len(metrics[2]) == 1
    if size_metrics_names == "foo":
        assert len(metrics[1]) == 1
    if amount_metrics_names == "foo":
        assert len(metrics[0]) == 1


def test_files_create_dir(create_temp_dir: Path, create_temp_file: Path) -> None:
    with raises(RuntimeError):
        files.create_dir(path=create_temp_file)

    files.create_dir(path=create_temp_dir)


@patch("arch_release_promotion.files.Settings")
@patch("arch_release_promotion.files.Upstream.get_releases")
def test_projectfiles(
    get_releases_mock: Mock,
    settings_mock: Mock,
    project_config: config.ProjectConfig,
) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        sync_dir = Path(temp_dir) / Path("foo")
        settings_mock.GITLAB_URL = "https://foo.bar"
        get_releases_mock.return_value = ["1.0.0", "1.0.1", "1.0.2"]

        project_config.sync_config.directory = sync_dir  # type: ignore
        assert files.ProjectFiles(
            project_config=project_config,
            settings=settings_mock,
        )
        assert sync_dir.exists() and sync_dir.is_dir()


@mark.parametrize(
    "create_tmp_in_sync_dir, sync_version_changes, set_latest_version_changes, remove_obsolete_changes",
    [
        (True, True, True, True),
        (True, True, True, False),
        (True, True, False, True),
        (True, False, False, False),
        (True, False, True, False),
        (True, False, True, True),
        (False, True, True, True),
        (False, True, True, False),
        (False, True, False, True),
        (False, False, False, False),
        (False, False, True, False),
        (False, False, True, True),
    ],
)
@patch("arch_release_promotion.files.Settings")
@patch("arch_release_promotion.files.Upstream.get_releases")
@patch("arch_release_promotion.files.Path")
@patch("arch_release_promotion.files.ProjectFiles._sync_version")
@patch("arch_release_promotion.files.ProjectFiles._set_latest_version_symlink")
@patch("arch_release_promotion.files.ProjectFiles._remove_obsolete_releases")
@patch("arch_release_promotion.files.ProjectFiles._set_last_update_file_timestamp")
def test_projectfiles_sync(
    _set_last_update_file_timestamp_mock: Mock,
    _remove_obsolete_releases_mock: Mock,
    _set_latest_version_symlink_mock: Mock,
    _sync_version_mock: Mock,
    path_mock: Mock,
    get_releases_mock: Mock,
    settings_mock: Mock,
    create_tmp_in_sync_dir: bool,
    sync_version_changes: bool,
    set_latest_version_changes: bool,
    remove_obsolete_changes: bool,
    project_config: config.ProjectConfig,
) -> None:
    promoted_releases = ["1.0.0", "1.0.1", "1.0.2"]
    temp_dir_base = Path("foo")
    path_mock.return_value = temp_dir_base
    _sync_version_mock.return_value = sync_version_changes
    _set_latest_version_symlink_mock.return_value = set_latest_version_changes
    _remove_obsolete_releases_mock.return_value = remove_obsolete_changes
    with tempfile.TemporaryDirectory() as temp_dir:
        sync_dir = Path(temp_dir) / Path("foo")
        settings_mock.GITLAB_URL = "https://foo.bar"
        get_releases_mock.return_value = promoted_releases

        project_config.sync_config.directory = sync_dir  # type: ignore

        if create_tmp_in_sync_dir:
            stale_tmp_dir = sync_dir / Path(".tmp-foo")
            (sync_dir / Path("foo2")).mkdir(parents=True)
            stale_tmp_dir.mkdir(parents=True)

        files.ProjectFiles.sync(
            project_config=project_config,
            settings=settings_mock,
        )
        assert sync_dir.exists() and sync_dir.is_dir()
        if create_tmp_in_sync_dir:
            assert not stale_tmp_dir.exists()

        _sync_version_mock.assert_has_calls(
            [call(temp_dir_base=temp_dir_base, version=release_version) for release_version in promoted_releases]
        )
        _set_latest_version_symlink_mock.assert_called_once()
        _remove_obsolete_releases_mock.assert_called_once()
        if any([sync_version_changes, set_latest_version_changes, remove_obsolete_changes]):
            _set_last_update_file_timestamp_mock.assert_called_once()


@mark.parametrize(
    "has_last_updated_file",
    [
        (True),
        (False),
    ],
)
def test_projectfiles__set_last_update_file_timestamp(
    has_last_updated_file: bool,
    project_files: files.ProjectFiles,
) -> None:
    if has_last_updated_file:
        file = project_files.project_config.sync_config.directory / Path("foo")  # type: ignore
        project_files.project_config.sync_config.last_updated_file = file  # type: ignore

    project_files._set_last_update_file_timestamp()


@mark.parametrize(
    "has_promoted_releases, create_files",
    [
        (True, True),
        (True, False),
        (False, True),
        (False, False),
    ],
)
def test_projectfiles__remove_obsolete_releases(
    has_promoted_releases: bool,
    create_files: bool,
    project_files: files.ProjectFiles,
) -> None:
    name = "foo"
    version = "0.1.0"
    other_version = "0.0.1"
    release_type_dir = project_files.project_config.sync_config.directory / Path(name)  # type: ignore
    release_type_dir.mkdir()
    version_dir = Path(f"{name}-{version}")
    (release_type_dir / version_dir).mkdir()

    if has_promoted_releases:
        project_files.promoted_releases = ["0.1.0"]
        project_files.project_config.releases = [
            config.ReleaseConfig(
                **{
                    "amount_metrics": [],
                    "create_torrent": False,
                    "extensions_to_sign": [],
                    "name": name,
                    "size_metrics": [],
                    "version_metrics": [],
                }
            )
        ]
    else:
        project_files.promoted_releases = []

    if create_files:
        other_version_dir = release_type_dir / Path(f"{name}-{other_version}")
        other_version_dir.mkdir()
        (other_version_dir / Path("foo.txt")).touch()
        (release_type_dir / Path(f"{name}-{other_version}.json")).touch()
        (release_type_dir / Path(f"{name}-{other_version}.torrent")).touch()

    project_files._remove_obsolete_releases()


@mark.parametrize(
    "has_promoted_releases, link_target",
    [
        (True, "other_version"),
        (True, "same_version"),
        (True, "file"),
        (True, "dir"),
        (True, None),
        (False, "other_version"),
        (False, "same_version"),
        (False, "file"),
        (False, "dir"),
        (False, None),
    ],
)
def test_projectfiles__set_latest_version_symlink(
    has_promoted_releases: bool,
    link_target: str,
    project_files: files.ProjectFiles,
) -> None:
    name = "foo"
    version = "0.1.0"
    other_version = "0.0.1"
    release_type_dir = project_files.project_config.sync_config.directory / Path(name)  # type: ignore
    release_type_dir.mkdir()
    latest_path = release_type_dir / Path("latest")
    version_dir = Path(f"{name}-{version}")
    (release_type_dir / version_dir).mkdir()

    if has_promoted_releases:
        project_files.promoted_releases = ["0.1.0"]
        project_files.project_config.releases = [
            config.ReleaseConfig(
                **{
                    "amount_metrics": [],
                    "create_torrent": False,
                    "extensions_to_sign": [],
                    "name": name,
                    "size_metrics": [],
                    "version_metrics": [],
                }
            )
        ]
    else:
        project_files.promoted_releases = []

    if link_target == "same_version":
        latest_path.symlink_to(version_dir)
    if link_target == "other_version":
        other_dir = Path(f"{name}-{other_version}")
        (release_type_dir / other_dir).mkdir()
        latest_path.symlink_to(other_dir)
    if link_target == "file":
        other_dir = Path(f"{name}-{other_version}")
        (release_type_dir / other_dir).touch()
        latest_path.symlink_to(other_dir)
    if link_target == "dir":
        latest_path.mkdir()

    project_files._set_latest_version_symlink()
    if has_promoted_releases:
        assert latest_path.exists() and latest_path.is_symlink() and latest_path.readlink() == version_dir


@mark.parametrize(
    "requires_sync, create_json_files",
    [
        (True, True),
        (True, False),
        (False, True),
        (False, False),
    ],
)
@patch("arch_release_promotion.files.Path")
@patch("arch_release_promotion.files.Upstream.download_promotion_artifact")
@patch("arch_release_promotion.files.extract_zip_file_to_parent_dir")
@patch("arch_release_promotion.files.ProjectFiles._project_version_requires_sync")
@patch("arch_release_promotion.files.Upstream.download_release")
@patch("arch_release_promotion.files.load_release_from_json_payload")
@patch("arch_release_promotion.files.ProjectFiles.copy_release_type_promotion_artifacts_to_build_dir")
@patch("arch_release_promotion.files.ProjectFiles.validate_release_type_files")
@patch("arch_release_promotion.files.ProjectFiles.move_release_type_to_sync_dir")
def test_projectfiles__sync_version(
    move_release_type_to_sync_dir_mock: Mock,
    validate_release_type_files_mock: Mock,
    copy_release_type_promotion_artifacts_to_build_dir_mock: Mock,
    load_release_from_json_payload_mock: Mock,
    download_release_mock: Mock,
    _project_version_requires_sync_mock: Mock,
    extract_zip_file_to_parent_dir_mock: Mock,
    download_promotion_artifact_mock: Mock,
    path_mock: Mock,
    requires_sync: bool,
    create_json_files: bool,
    create_temp_dir: Path,
    project_files: files.ProjectFiles,
) -> None:
    version = "0.1.0"
    promotion_temp_dir = create_temp_dir / Path("promotion")
    build_temp_dir = create_temp_dir / Path("build")
    promotion_temp_dir.mkdir()
    build_temp_dir.mkdir()
    path_mock.side_effect = [promotion_temp_dir, build_temp_dir]

    promotion_artifact = promotion_temp_dir / Path("promotion.zip")
    download_promotion_artifact_mock.return_value = promotion_artifact

    _project_version_requires_sync_mock.return_value = requires_sync

    build_artifact = build_temp_dir / Path("output.zip")
    download_release_mock.return_value = build_artifact

    if create_json_files:
        (promotion_temp_dir / Path("foo")).mkdir()
        (promotion_temp_dir / Path("foo/foo-0.1.0.json")).touch()

    project_files._sync_version(temp_dir_base=None, version=version)
    extract_zip_file_to_parent_dir_mock.assert_has_calls(
        [call(path=promotion_artifact), call(path=build_artifact)] if requires_sync else [call(path=promotion_artifact)]
    )
    if create_json_files and requires_sync:
        copy_release_type_promotion_artifacts_to_build_dir_mock.assert_called_once()
        validate_release_type_files_mock.assert_called_once()
        move_release_type_to_sync_dir_mock.assert_called_once()


@mark.parametrize(
    "create_json, has_torrent, create_torrent_file, create_release_file, return_value",
    [
        (True, True, True, True, True),
        (True, False, True, True, True),
        (True, False, False, True, True),
        (True, True, False, True, False),
        (False, False, False, True, False),
        (True, False, False, False, False),
    ],
)
@patch("arch_release_promotion.files.load_release_from_json_payload")
def test_projectfiles__is_release_type_synced(
    load_release_from_json_payload_mock: Mock,
    create_json: bool,
    has_torrent: bool,
    create_torrent_file: bool,
    create_release_file: bool,
    return_value: bool,
    project_files: files.ProjectFiles,
) -> None:
    name = "foo"
    version = "0.1.0"
    file = "foo.txt"

    (project_files.project_config.sync_config.directory / Path(f"{name}")).mkdir(parents=True)  # type: ignore
    if create_json:
        (
            project_files.project_config.sync_config.directory / Path(f"{name}/{name}-{version}.json")  # type: ignore
        ).touch()

    load_release_from_json_payload_mock.return_value = (
        files.Release(
            **{
                "name": name,
                "version": version,
                "files": [file],
                "amount_metrics": [],
                "size_metrics": [],
                "version_metrics": [],
                "torrent_file": f"{name}-{version}.torrent" if has_torrent else None,
                "developer": "Foobar McFooface <foobar@mcfooface.com>",
                "pgp_public_key": "SOMEONESKEY",
            }
        )
        if create_json
        else None
    )

    if create_torrent_file:
        (
            project_files.project_config.sync_config.directory  # type: ignore
            / Path(f"{name}/{name}-{version}.torrent")
        ).touch()

    if create_release_file:
        (project_files.project_config.sync_config.directory / Path(f"{name}/{name}-{version}")).mkdir(  # type: ignore
            parents=True
        )
        (
            project_files.project_config.sync_config.directory / Path(f"{name}/{name}-{version}/{file}")  # type: ignore
        ).touch()

    assert project_files._is_release_type_synced(name=name, version=version) is return_value


@mark.parametrize(
    "has_release_type, release_type_synced, return_value",
    [
        (True, False, True),
        (True, True, False),
        (False, True, False),
        (False, False, False),
    ],
)
@patch("arch_release_promotion.files.ProjectFiles._is_release_type_synced")
def test_projectfiles__project_version_requires_sync(
    _is_release_type_synced_mock: Mock,
    has_release_type: bool,
    release_type_synced: bool,
    return_value: bool,
    project_files: files.ProjectFiles,
) -> None:
    name = "foo"
    version = "0.1.0"
    if has_release_type:
        project_files.project_config.releases = [
            config.ReleaseConfig(
                **{
                    "amount_metrics": [],
                    "create_torrent": False,
                    "extensions_to_sign": [],
                    "name": name,
                    "size_metrics": [],
                    "version_metrics": [],
                }
            )
        ]

    _is_release_type_synced_mock.return_value = release_type_synced

    assert project_files._project_version_requires_sync(version=version) is return_value


@mark.parametrize("torrent_file", [(True), (False)])
def test_projectfiles_copy_release_type_promotion_artifacts_to_build_dir(
    torrent_file: bool,
    create_temp_dir: Path,
    project_files: files.ProjectFiles,
) -> None:
    torrent_file_name = "foo-1.0.0.torrent"
    release_dir_name = "foo-1.0.0"
    release_type = release.Release(
        name="foo",
        version="1.0.0",
        files=["foo", "bar", "baz"],
        amount_metrics=[],
        size_metrics=[],
        version_metrics=[],
        developer="Foobar McFoo",
        torrent_file=torrent_file_name if torrent_file else None,
        pgp_public_key="SOMEONESKEY",
    )
    source_base = create_temp_dir / Path("source")
    (source_base / Path(f"foo/{release_dir_name}")).mkdir(parents=True)
    (source_base / Path("foo/foo-1.0.0.json")).touch()
    if torrent_file:
        (source_base / Path(f"foo/{torrent_file_name}")).touch()

    destination_base = create_temp_dir / Path("destination")
    (destination_base / Path(f"foo/{release_dir_name}")).mkdir(parents=True)

    files.ProjectFiles.copy_release_type_promotion_artifacts_to_build_dir(
        release_type=release_type,
        source_base=source_base,
        destination_base=destination_base,
    )


@mark.parametrize(
    "create_json, require_torrent, create_torrent, create_file, expectation",
    [
        (True, True, True, True, does_not_raise()),
        (False, True, True, True, raises(RuntimeError)),
        (True, True, False, True, raises(RuntimeError)),
        (True, True, True, False, raises(RuntimeError)),
    ],
)
def test_projectfiles_validate_release_type_files(
    create_json: bool,
    require_torrent: bool,
    create_torrent: bool,
    create_file: bool,
    expectation: ContextManager[str],
    create_temp_dir: Path,
    project_files: files.ProjectFiles,
) -> None:
    torrent_file_name = "foo-1.0.0.torrent"
    release_dir_name = "foo-1.0.0"
    release_type = release.Release(
        name="foo",
        version="1.0.0",
        files=["foo", "bar", "baz"],
        amount_metrics=[],
        size_metrics=[],
        version_metrics=[],
        developer="Foobar McFoo",
        torrent_file=torrent_file_name if require_torrent else None,
        pgp_public_key="SOMEONESKEY",
    )
    (create_temp_dir / Path(f"foo/{release_dir_name}")).mkdir(parents=True)

    if create_json:
        (create_temp_dir / Path("foo/foo-1.0.0.json")).touch()
    if create_torrent:
        (create_temp_dir / Path(f"foo/{torrent_file_name}")).touch()
    if create_file:
        (create_temp_dir / Path(f"foo/{release_dir_name}/foo")).touch()
        (create_temp_dir / Path(f"foo/{release_dir_name}/bar")).touch()
        (create_temp_dir / Path(f"foo/{release_dir_name}/baz")).touch()

    with expectation:
        files.ProjectFiles.validate_release_type_files(release_type=release_type, path=create_temp_dir)


@mark.parametrize(
    "has_torrent, create_destination_as_file, create_destination_as_dir",
    [
        (False, False, False),
        (True, False, False),
        (True, False, True),
        (True, True, False),
        (True, False, True),
    ],
)
def test_projectfiles_move_release_type_to_sync_dir(
    has_torrent: bool,
    create_destination_as_file: bool,
    create_destination_as_dir: bool,
    create_temp_dir: Path,
    project_files: files.ProjectFiles,
) -> None:
    torrent_file_name = "foo-1.0.0.torrent"
    release_dir_name = "foo-1.0.0"
    release_type = release.Release(
        name="foo",
        version="1.0.0",
        files=["foo", "bar", "baz"],
        amount_metrics=[],
        size_metrics=[],
        version_metrics=[],
        developer="Foobar McFoo <foobar@mcfooface.com>",
        torrent_file=torrent_file_name if has_torrent else None,
        pgp_public_key="SOMEONESKEY",
    )
    source_base = create_temp_dir / Path("source")
    sync_dir = create_temp_dir / Path("sync_dir")

    (source_base / Path(f"foo/{release_dir_name}")).mkdir(parents=True)
    for file in release_type.files:
        (source_base / Path(f"foo/{release_dir_name}/{file}")).touch()
    (source_base / Path(f"foo/{release_dir_name}.json")).touch()

    if has_torrent:
        (source_base / Path(f"foo/{release_dir_name}.torrent")).touch()

    if create_destination_as_file:
        (sync_dir / Path("foo")).mkdir(parents=True)
        (sync_dir / Path(f"foo/{release_dir_name}")).touch()

    if create_destination_as_dir:
        (sync_dir / Path(f"foo/{release_dir_name}")).mkdir(parents=True)

    files.ProjectFiles.move_release_type_to_sync_dir(release=release_type, source_base=source_base, sync_dir=sync_dir)
