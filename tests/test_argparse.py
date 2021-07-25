from argparse import ArgumentParser, ArgumentTypeError
from contextlib import nullcontext as does_not_raise
from typing import ContextManager

from pytest import mark, raises

from arch_release_promotion import argparse


def test_argparse_argparsefactory() -> None:
    assert isinstance(argparse.ArgParseFactory(), argparse.ArgParseFactory)


def test_argparse_promote() -> None:
    assert isinstance(argparse.ArgParseFactory().promote(), ArgumentParser)


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
