======================
arch-release-promotion
======================

This project allows for promoting existing releases of a project in Arch
Linux's Gitlab instance.

Releases of a project (e.g. ``project``) may consist of several release types
(e.g. ``image_a`` and ``image_b``), which are addressed separately.

A promotion encompasses - per release type - PGP signatures for relevant
artifacts (optional), a torrent file (optional) and a JSON payload which can be
used by `archweb <https://github.com/archlinux/archweb>`_ to display
information about each release type.

Requirements
============

The arch-release-promotion tool is Python based. All requirements are specified
in its `pyproject.toml <pyproject.toml>`_.

Configuration
=============

The command-line tool ``arch-release-promotion`` makes use of two sources of configuration:

* `makepkg.conf <https://man.archlinux.org/man/makepkg.conf.5>`_ is read from
  any of its locations in the same priority as `makepkg
  <https://man.archlinux.org/man/makepkg.8>`_ does.
  All of the below can also be based to the tool via environment variables:

  * ``GPGKEY`` is recognized for establishing which PGP key to use for signing
  * ``PACKAGER`` is recognized for establishing who is doing the signature and
    is important for `WKD
    <https://wiki.archlinux.org/title/GnuPG#Web_Key_Directory>`_ lookup
  * ``MIRRORLIST_URL`` (not used by makepkg) is used during the generation of torrent files to add
    webseeds (defaults to
    ``"https://archlinux.org/mirrorlist/?country=all&protocol=http&protocol=https"``)
  * ``GITLAB_URL`` (not used by makepkg) is used to connect to a GitLab instance to select, download
    and promote releases of a project (defaults to
    ``"https://gitlab.archlinux.org"``)
  * ``PRIVATE_TOKEN`` (not used by makepkg) is used to authenticate against the
    GitLab instance. The `personal access token
    <https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html>`_
    needs to provide write access for the target project.

* `projects.toml` is a configuration file that provides the configuration for a
  project and its releases. Configuration files are read and merged with
  descending priority from ``/etc/arch-release-promotion/projects.toml`` and
  ``$XDG_CONFIG_HOME/arch-release-promotion/projects.toml`` (which defaults to
  ``$HOME/.config/arch-release-promotion/projects.toml`` if
  ``$XDG_CONFIG_HOME`` is unset).
  Please refer to the `example file <examples/projects.toml>`_ for further
  reference in regards to the available options

Use
===

After installation, refer to the output of ``arch-release-promotion -h``.


JSON payload
============

The promotion of a release encompasses one or more JSON payloads, that describe
each release type in the release.

.. code:: json

   {
     "developer": "Foobar McFooface <foobar@mcfooface.com>",
     "files": ["something.txt", "something.txt.sig"],
     "info": [
       {
         "bar": {
           "description": "Version of bar",
           "version": "0.3.0"
         }
       }
     ],
     "name": "foo",
     "pgp_public_key": "SOMEONESPGPKEYID",
     "torrent_file": "foo-0.1.0.torrent",
     "version": "0.1.0"
   }

* ``developer``: The full uid of the person promoting (and optionally signing
  artifacts in) the release type.
* ``files``: A list of files in the release type.
* ``info`` (optional): Additional info about the (creation of) the release
  type. The value depends on whether configuration of the release type defines
  at least one value in its list of ``info_metrics`` and whether this is found
  in the release's metrics file.
* ``name``: The name of the release type.
* ``pgp_public_key``: The PGP key ID of the key signing files in the release
  type.
* ``torrent_file`` (optional): The name of a torrent file created for the
  release type. The value depends on whether the configuration for the release
  type sets ``create_torrent`` to ``True``.
* ``version``: The version of the release type.

License
=======

Arch-release-promotion is licensed under the terms of the **GPL-3.0-or-later** (see `LICENSE <LICENSE>`_).
