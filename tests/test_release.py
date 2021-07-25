from arch_release_promotion import release


def test_release() -> None:
    assert release.Release(
        name="foo",
        version="0.1.0",
        files=["foo", "bar", "baz"],
        info={"bar": {"description": "Version of bar when building foo", "version": "1.0.0"}},
        developer="Foobar McFoo",
        torrent_file="foo-0.1.0.torrent",
        pgp_public_key="SOMEONESKEY",
    )
