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

Use
===

After installation, refer to the output of ``arch-release-promotion -h``.

Configuration
=============

The command-line tool ``arch-release-promotion`` makes use of two sources of configuration:

* `makepkg.conf <https://man.archlinux.org/man/makepkg.conf.5>`_ is read from
  any of its locations in the same priority as `makepkg
  <https://man.archlinux.org/man/makepkg.8>`_ does.
  All of the below can also be passed to the tool via environment variables:

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

* ``projects.toml`` is a configuration file that provides the configuration for a
  project and its releases. Configuration files are read and merged with
  descending priority from ``/etc/arch-release-promotion/projects.toml`` and
  ``$XDG_CONFIG_HOME/arch-release-promotion/projects.toml`` (which defaults to
  ``$HOME/.config/arch-release-promotion/projects.toml`` if
  ``$XDG_CONFIG_HOME`` is unset).
  Please refer to `examples/example.toml <examples/example.toml>`_ for further
  reference in regards to the available options

Openmetrics
-----------

If the upstream project offers an `openmetrics <https://openmetrics.io/>`_
based metrics file, the data from it can be used as additional information in
the JSON payload.

The following metrics are considered.

Version metrics
^^^^^^^^^^^^^^^

Description and version information about e.g. packages can be derived from
``version_info`` metrics of type ``info``, that define a ``name``,
``description`` and ``version`` label.

For the metrics to be considered, they have to be configured by adding a
``version_metrics`` list (a list of names to look for) to a release of a
project.

.. code::

   # TYPE version_info info
   # HELP version_info Package description and version information
   version_info{name="my-package",description="Version of my-package used for build",version="1.0.0-1"} 1

The above metrics entry would result in the following JSON representation:

.. code:: json

   "version_metrics": [
     {
       "name": "my-package",
       "description": "Version of my-package used for build",
       "version": "1.0.0-1"
     }
   ]

Size metrics
^^^^^^^^^^^^

Artifact size information in MebiBytes (MiB) and description can be derived
from ``artifact_bytes`` metrics of type ``gauge``, that define a ``name`` and a
``description`` label.

For the metrics to be considered, they have to be configured by adding a
``size_metrics`` list (a list of names to look for) to a release of a
project.

.. code::

   # TYPE artifact_bytes gauge
   # HELP artifact_bytes Artifact sizes in Bytes
   artifact_bytes{name="foo",description="Size of foo in MiB"} 832

The above metrics entry would result in the following JSON representation:

.. code:: json

   "size_metrics": [
     {
       "name": "foo",
       "description": "Size of foo in MiB",
       "size": 832
     }
   ]

Amount metrics
^^^^^^^^^^^^^^

Information on the amount of something (e.g. packages) and description can be
derived from ``data_count`` metrics of type ``summary``, that define a ``name``
and a ``description`` label.

For the metrics to be considered, they have to be configured by adding a
``amount_metrics`` list (a list of names to look for) to a release of a
project.

.. code::

   # TYPE data_count summary
   # HELP data_count The amount of something used in some context
   data_count{name="foo",description="The amount of packages in foo"} 369

The above metrics entry would result in the following JSON representation:

.. code:: json

   "amount_metrics": [
     {
       "name": "foo",
       "description": "The amount of packages in foo",
       "amount": 369
     }
   ]

Promotion artifact
==================

The promotion artifact is a ZIP compressed file (``promotion.zip``), that is
uploaded to the project before its link is added to the release that it is
promoting.

The file contains one directory for each release type that the project offers.
In each release type directory there are is a **JSON payload**
(``<release_type>-<version>.json``), a directory
(``<release_type>-<version>/``) containing signatures for any files that have
been setup for detached signatures and optionally a torrent file
(``<release_type>-<version>.json``) that is created for the release type's
build artifacts *and* the detached signatures contained in the promotion
artifact.

.. code::

   example
   ├── example-0.1.0
   │   └── artifact.tar.gz.sig
   ├── example-0.1.0.json
   └── example-0.1.0.torrent

JSON payload
------------

The promotion of a release encompasses one or more JSON payloads, that describe
each release type in the release.

.. code:: json

   {
     "amount_metrics": [
       {
         "name": "foo",
         "description": "The amount of packages in foo",
         "size": 369
       }
     ],
     "developer": "Foobar McFooface <foobar@mcfooface.com>",
     "files": ["something.txt", "something.txt.sig"],
     "name": "foo",
     "pgp_public_key": "SOMEONESPGPKEYID",
     "size_metrics": [
       {
         "name": "foo",
         "description": "Size of foo in MiB",
         "size": 832
       }
     ],
     "torrent_file": "foo-0.1.0.torrent",
     "version_metrics": [
       {
         "name": "my-package",
         "description": "Version of my-package used for build",
         "version": "1.0.0-1"
       }
     ],
     "version": "0.1.0"
   }

* ``amount_metrics``: A list of objects that describe the amount of something
  (optional). The list depends on whether the project's configuration defines
  ``amount_metrics`` and whether those metrics are available in the specific
  release.
* ``developer``: The full uid of the person promoting (and optionally signing
  artifacts in) the release type.
* ``files``: A list of files in the release type.
* ``name``: The name of the release type.
* ``pgp_public_key``: The PGP key ID of the key signing files in the release
  type.
* ``size_metrics``: A list of objects that describe the size of something
  (optional). The list depends on whether the project's configuration defines
  ``size_metrics`` and whether those metrics are available in the specific
  release.
* ``torrent_file`` (optional): The name of a torrent file created for the
  release type. The value depends on whether the configuration for the release
  type sets ``create_torrent`` to ``True``.
* ``version_metrics``: A list of objects that describe the version of something
  (optional). The list depends on whether the project's configuration defines
  ``version_metrics`` and whether those metrics are available in the specific
  release.
* ``version``: The version of the release type.

License
=======

Arch-release-promotion is licensed under the terms of the **GPL-3.0-or-later** (see `LICENSE <LICENSE>`_).
