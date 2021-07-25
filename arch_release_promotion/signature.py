from pathlib import Path
from subprocess import run
from typing import List


def sign_files_in_dir(path: Path, developer: str, gpgkey: str, file_extensions: List[str] = []) -> None:
    """Create a detached PGP signature for one or more files in a release

    Parameters
    ----------
    path: Path
        The path to the release
    developer: str
        The developer mbox (i.e. "First Last <user@domain.tld>")
    gpgkey: str
        The PGP key to sign with
    """

    for _file in path.iterdir():
        if _file.suffix in file_extensions:
            print(f"Creating signature for {_file}...")
            return_code = 255
            while return_code != 0:
                return_code = sign_file(path=_file.resolve(), developer=developer, gpgkey=gpgkey)
            print("Done!")


def sign_file(path: Path, developer: str, gpgkey: str) -> int:
    """Sign a file and return the status code of gpg

    Parameters
    ----------
    path: Path
        The path to a file to sign
    developer: str
        The developer mbox (i.e. "First Last <user@domain.tld>")
    gpgkey: str
        The PGP key to sign with

    Returns
    -------
    int
        The returncode of the gpg process
    """

    return run(
        [
            "gpg",
            "--sender",
            developer,
            "--default-key",
            gpgkey,
            "--detach-sign",
            str(path),
        ],
    ).returncode
