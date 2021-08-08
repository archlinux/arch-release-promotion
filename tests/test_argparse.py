from argparse import ArgumentParser, ArgumentTypeError
from contextlib import nullcontext as does_not_raise
from typing import ContextManager
from unittest.mock import Mock, call, patch

from pytest import mark, raises

from arch_release_promotion import argparse


def test_argparse_argparsefactory() -> None:
    assert isinstance(argparse.ArgParseFactory(), argparse.ArgParseFactory)


@patch("argparse.ArgumentParser.parse_args")
@patch("arch_release_promotion.argparse.exit")
@patch("arch_release_promotion.argparse.metadata")
def test_argparse_promote(metadata_mock: Mock, exit_mock: Mock, parse_args_mock: Mock) -> None:
    assert isinstance(argparse.ArgParseFactory.promote(), ArgumentParser)
    assert call.version("arch_release_promotion") in metadata_mock.mock_calls
    exit_mock.assert_called_once()

    parse_args_mock.return_value = Mock(version=False)
    assert isinstance(argparse.ArgParseFactory.promote(), ArgumentParser)


@mark.parametrize(
    "input_string, expectation",
    [
        ("foo", does_not_raise()),
        ("foo/bar", does_not_raise()),
        ("", raises(ArgumentTypeError)),
    ],
)
def test_argparse_non_zero_string(input_string: str, expectation: ContextManager[str]) -> None:
    with expectation:
        argparse.ArgParseFactory.non_zero_string(input_=input_string)
