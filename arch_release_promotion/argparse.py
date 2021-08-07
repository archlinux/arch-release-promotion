import argparse
from importlib import metadata
from sys import exit


class ArgParseFactory:
    """A factory class to create different types of argparse.ArgumentParser instances

    Attributes
    ----------
    parser: argparse.ArgumentParser
        The instance's ArgumentParser instance, which is created with a default verbose argument

    """

    def __init__(self, prog: str = "program", description: str = "default") -> None:
        self.parser = argparse.ArgumentParser(prog=prog, description=description)
        self.parser.add_argument(
            "-v",
            "--verbose",
            action="store_true",
            help="verbose output",
        )
        self.parser.add_argument(
            "-V",
            "--version",
            action="store_true",
            help="version information",
        )

    @classmethod
    def promote(self) -> argparse.ArgumentParser:
        """A class method to create an ArgumentParser for promotion

        Returns
        -------
        argparse.ArgumentParser
            An ArgumentParser instance specific for promotion
        """

        instance = self(
            prog="arch-release-promotion",
            description="Download release artifacts from a project and promote them",
        )
        instance.parser.add_argument(
            "-p",
            "--project",
            type=self.non_zero_string,
            help=(
                "the project on a remote to sign (e.g. 'group/project'). "
                f"By default {instance.parser.prog} attempts to promote releases for "
                "all projects specified in its config"
            ),
        )
        instance.parser.add_argument(
            "-r",
            "--release",
            type=self.non_zero_string,
            help=(
                "the release of a project to sign (e.g. '0.1.0'). "
                f"By default {instance.parser.prog} requires user input to select a release."
            ),
        )
        if instance.parser.parse_args().version:
            print(f"{instance.parser.prog} {metadata.version('arch_release_promotion')}")
            exit(0)

        return instance.parser

    @classmethod
    def non_zero_string(self, input_: str) -> str:
        """Validate a string to be of non_zero length

        Parameters
        ----------
        input_: str
            A string

        Raises
        ------
        argparse.ArgumentTypeError:
            If a string is of zero length

        Returns
        -------
        str
            A string that is of non-zero length
        """

        if len(input_) < 1:
            raise argparse.ArgumentTypeError("the provided string can not be empty")
        return input_
