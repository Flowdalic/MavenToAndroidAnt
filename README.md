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


### Common Syntax

Create a comma separated file names `artifacts.csv` in your project with he following syntax:

```
<group>,<artifactId>,<version>,<fingerprint>
```

### Version Variables

If you have multiple artifacts sharing the same version, thenm you may want to use version variables.
Declare them with
```
<versionVariable>=<version>
smackVersion=4.1.7
```

After that, you can use `$<versionVariable>` everywhere instead of the version String, e.g.
```
org.igniterealtime.smack,smack-tcp,$smackVersion,1357B01865B2503C18453D208CAC2A9678548E35
```

### Invocation

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
