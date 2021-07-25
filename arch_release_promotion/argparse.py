import argparse


class ArgParseFactory:
    """A factory class to create different types of argparse.ArgumentParser instances

    Attributes
    ----------
    parser: argparse.ArgumentParser
        The instance's ArgumentParser instance, which is created with a default verbose argument

    """

    def __init__(self, description: str = "default") -> None:
        self.parser = argparse.ArgumentParser(description=description)
        self.parser.add_argument(
            "-v",
            "--verbose",
            action="store_true",
            help="verbose output",
        )

    @classmethod
    def promote(self) -> argparse.ArgumentParser:
        """A class method to create an ArgumentParser for promotion

        Returns
        -------
        argparse.ArgumentParser
            An ArgumentParser instance specific for promotion
        """

        instance = self(description="Download release artifacts from a project and promote them")
        instance.parser.add_argument(
            "name",
            type=self.non_zero_string,
            help="the project on a remote to sign (e.g. 'group/project')",
        )

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
            raise argparse.ArgumentTypeError("the provided project name can not be zero")
        return input_
