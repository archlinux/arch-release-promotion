======================
arch-release-promotion
======================

This project allows for promoting existing releases of a project in Arch
Linux's Gitlab instance.
A promotion encompasses PGP signatures for relevant release artifacts, a
.torrent file, that is created for each release type and a JSON payload per
release type which can be used by archweb to display information about the
release correctly.

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

License
=======

Arch-release-promotion is licensed under the terms of the **GPL-3.0-or-later** (see `LICENSE <LICENSE>`_).
