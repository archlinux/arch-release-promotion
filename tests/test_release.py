from arch_release_promotion import release


def test_metric() -> None:
    assert release.Metric(
        name="foo",
        description="bar",
    )


def test_amount_metric() -> None:
    assert release.AmountMetric(
        name="foo",
        description="bar",
        amount=1,
    )


def test_size_metric() -> None:
    assert release.SizeMetric(
        name="foo",
        description="bar",
        size=1.1,
    )


def test_version_metric() -> None:
    assert release.VersionMetric(
        name="foo",
        description="bar",
        version="1.0.0-1",
    )


def test_release() -> None:
    assert release.Release(
        name="foo",
        version="0.1.0",
        files=["foo", "bar", "baz"],
        amount_metrics=[],
        size_metrics=[],
        version_metrics=[],
        developer="Foobar McFoo",
        torrent_file="foo-0.1.0.torrent",
        pgp_public_key="SOMEONESKEY",
    )
