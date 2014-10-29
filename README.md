MavenToAndroidAnt
=================

A Python3 script to fetch Maven artifacts from Maven Central and place them in an Android Ant Project.

Features
--------

- Will fetch the source artifact and install it correctly in Android Ant Projects so that the artifact source is shown when the debugger enters the code of the artifact
- Verifies the artifacts detachted signature against an expected *fingerprint*. Will download the public key if it is missing
- Supports non-SNAPSHOT and SNAPSHOT artifacts

Requirements
------------

- Python3
- python-gnupg

Optional Dependencies
---------------------

- httplib2 - for caching

Usage
-----

Create a comma separated file names `artifacts.csv` in your project with he following syntax:

```
<group>,<artifactId>,<version>,<fingerprint>
```

Use

```
getMavenArtifactsNG.py -p <projectdir>
````

to download the artifacts

Legacy Script
-------------

`getMavenArtifacts.py` is the legacy version of the script.
There is no reason to use it any more.
It soley exists for legacy reasons and is no longer maintained.
