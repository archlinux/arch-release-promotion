import tempfile
from pathlib import Path
from unittest.mock import Mock, call, patch

from arch_release_promotion import signature


@patch("arch_release_promotion.signature.sign_file")
def test_sign_files_in_dir(sign_file_mock: Mock) -> None:
    developer = "foo bar <foo@bar.baz>"
    gpgkey = "somefakekey"
    sign_file_mock.return_value = 0

    with tempfile.TemporaryDirectory() as temp_dir:
        tempfile.NamedTemporaryFile(suffix=".foo", dir=temp_dir, delete=False)
        extensions = [".bar", ".baz"]
        for suffix in extensions:
            tempfile.NamedTemporaryFile(suffix=suffix, dir=temp_dir, delete=False)

        signature.sign_files_in_dir(path=Path(temp_dir), developer=developer, gpgkey=gpgkey, file_extensions=extensions)


@patch("arch_release_promotion.signature.run")
def test_sign_file(run_mock: Mock) -> None:
    developer = "foo bar <foo@bar.baz>"
    gpgkey = "somefakekey"
    path = Path("/foo/bar.baz")
    calls = [
        call(
            [
                "gpg",
                "--sender",
                developer,
                "--default-key",
                gpgkey,
                "--detach-sign",
                str(path),
            ]
        )
    ]
    signature.sign_file(path=path, developer=developer, gpgkey=gpgkey)
    run_mock.assert_has_calls(calls=calls, any_order=True)
