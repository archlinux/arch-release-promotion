import tempfile
from pathlib import Path
from typing import Any, List
from unittest.mock import Mock, call, patch

from arch_release_promotion import signature


@patch("arch_release_promotion.signature.run")
def test_sign_files_in_dir(run_mock: Mock) -> None:
    developer = "foo bar <foo@bar.baz>"
    gpgkey = "somefakekey"
    calls: List[Any] = []
    with tempfile.TemporaryDirectory() as temp_dir:
        tempfile.NamedTemporaryFile(suffix=".foo", dir=temp_dir, delete=False)
        extensions = [".bar", ".baz"]
        for suffix in extensions:
            file_to_sign = tempfile.NamedTemporaryFile(suffix=suffix, dir=temp_dir, delete=False)
            calls += [
                call(
                    [
                        "gpg",
                        "--sender",
                        developer,
                        "--default-key",
                        gpgkey,
                        "--detach-sign",
                        str(Path(file_to_sign.name).resolve()),
                    ]
                )
            ]
        signature.sign_files_in_dir(path=Path(temp_dir), developer=developer, gpgkey=gpgkey, file_extensions=extensions)
        run_mock.assert_has_calls(calls=calls, any_order=True)
