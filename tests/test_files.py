import tempfile
import zipfile
from contextlib import nullcontext as does_not_raise
from pathlib import Path
from typing import ContextManager, Iterator, List

from pytest import fixture, mark, raises

from arch_release_promotion import files, release


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
