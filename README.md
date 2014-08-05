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

Usage
-----

Create a comma separated file in your project with he following syntax:

```
<group>,<artifactId>,<version>,<fingerprint>
```

Use

```
getMavenArtifacts -f <filename> -p <projectdir>
````

to download the artifacts
