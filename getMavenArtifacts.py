#!/usr/bin/env python3
import argparse
import urllib.request
import re
import os
import csv
import io
import gnupg
import sys

httplib2Available = True
try:
    import httplib2
    userHome = os.path.expanduser('~')
    httplib2CacheDir = userHome + '/.cache/httplib2'
    if not os.path.exists(httplib2CacheDir):
        os.makedirs(httplib2CacheDir)
    h = httplib2.Http(httplib2CacheDir)
except ImportError:
    httplib2Available = False

SONATYPE_RELEASE_URL = "https://oss.sonatype.org/content/repositories/releases"
SONATYPE_SNAPSHOT_URL = "https://oss.sonatype.org/content/repositories/snapshots"
SNAPSHOT = '-SNAPSHOT'
SOURCES_REGEX = re.compile('".*sources.jar"')
JAR_REGEX = re.compile('".*[0-9].jar"')

def downloadFile(url, dest):
  if httplib2Available:
    response, content = h.request(url)
    with open(dest, 'wb') as f:
      f.write(content)
  else:
    urllib.request.urlretrieve(url, dest)

def getDirectoryContent(url):
  if httplib2Available:
    response, content = h.request(url)
    return content.decode('utf-8')
  else:
    path = urllib.request.urlopen(remoteUrl)
    return path.read().decode('utf-8')

class MavenArtifact:
  def __init__(self, groupId, artifactId, version, pgpKeyFingerprint):
    self.groupId = groupId
    self.artifactId = artifactId
    self.version = version
    self.pgpKeyFingerprint = pgpKeyFingerprint

  def __str__(self):
    return self.groupId + ':' + self.artifactId + ':' + self.version

  def isSnapshot(self):
    return self.version.endswith(SNAPSHOT)

  def isNonSnapshot(self):
    return not self.isSnapshot()

  def getArtifactDirectoryUrl(self):
    directory = self.groupId.replace('.', '/')
    if self.isSnapshot():
      return SONATYPE_SNAPSHOT_URL + '/' + directory + '/' + self.artifactId + '/' + self.version 
    else:
      return SONATYPE_RELEASE_URL + '/' + directory + '/'  + self.artifactId + '/' + self.version

  def getArtifactIdAndVersion(self):
    if self.isSnapshot():
      version = self.version[:-len(SNAPSHOT)]
    else:
      version = self.version
    return self.artifactId + '-' + version

  def destFilenamePrefix(self):
    if self.isSnapshot():
      maybeSnapshot = SNAPSHOT
    else:
      maybeSnapshot = ""
    return self.getArtifactIdAndVersion() + maybeSnapshot

  def getJarUrl(self):
    if self.isNonSnapshot():
      return self.getArtifactDirectoryUrl() + '/' + self.getArtifactIdAndVersion() + '.jar'
    content = self.getRepositoryDirectoryContent()
    jars = JAR_REGEX.findall(content)
    jars.sort()
    newestJar = jars[-1]
    return newestJar.replace('"', '')

  def getJarSigUrl(self):
    if self.isSnapshot():
      raise ValueError("Snapshot releases contain no OpenPG signatures")
    return self.getJarUrl() + '.asc'

  def getSourceUrl(self):
    if self.isNonSnapshot():
      return self.getArtifactDirectoryUrl() + '/' + self.getArtifactIdAndVersion() + '-sources.jar'
    content = self.getRepositoryDirectoryContent()
    jars = SOURCES_REGEX.findall(content)
    jars.sort()
    newestJar = jars[-1]
    return newestJar.replace('"', '')

  def jarDestFilename(self):
    return self.destFilenamePrefix() + '.jar'

  def jarSigDestFilename(self):
    return self.jarDestFilename() + '.asc'

  def sourceDestFilename(self):
    return self.destFilenamePrefix() + '-sources.jar'

  def getRepositoryDirectoryContent(self):
    remoteUrl = self.getArtifactDirectoryUrl()
    content = getDirectoryContent(remoteUrl)
    return content

  def placeInProject(self, projectDir):
    libsDir = projectDir + '/libs/'
    libsSourcesDir = projectDir + '/libs-sources/'
    if not os.path.exists(libsDir):
      os.makedirs(libsDir)
    if not os.path.exists(libsSourcesDir):
      os.makedirs(libsSourcesDir)
    jarUrl = self.getJarUrl()
    jarDestFilename = self.jarDestFilename()
    jarDest = libsDir + jarDestFilename
    print("Downloading " + jarDestFilename + " to " + libsDir)
    downloadFile(jarUrl, jarDest)
    if self.isNonSnapshot():
      jarSigDestFilename = self.jarSigDestFilename()
      jarSigUrl = self.getJarSigUrl()
      jarSigDest = libsDir + jarSigDestFilename
      print("Downloading " + jarSigDestFilename + " to " + libsDir)
      downloadFile(jarSigUrl, jarSigDest)
    sourceUrl = self.getSourceUrl();
    sourceDestFilename = self.sourceDestFilename()
    sourceDest = libsSourcesDir + sourceDestFilename
    print("Downloading " + sourceDestFilename + " to " + libsSourcesDir)
    downloadFile(sourceUrl, sourceDest)
    f = open(jarDest + '.properties', 'w+')
    f.write('src=../libs-sources/' + sourceDestFilename)
    f.close()

  def installIn(self, projectDir):
    self.createDirStructure(projectDir)
    jar = projectDir + '/libs/' + self.jarDestFilename()
    jarSig = projectDir + '/libs/' + self.jarSigDestFilename()
    try:
      if os.path.exists(jar):
        if self.isSnapshot():
          print("Not fetching " + str(self) + " as artifact already exists in project")
          return
        if self.verifySignature(jarSig, jar):
          print("Not fetching " + str(self) + " as artifact already exists in project and signature is valid")
          return
    except:
      e = sys.exc_info()[0]
      print("Exception: " + str(e))
    self.deleteFromProject(projectDir)
    self.placeInProject(projectDir)
    if self.isNonSnapshot():
      if self.verifySignature(jarSig, jar):
        print("Successfully verified signature for " + jar)
      else:
        raise Exception("Could not verify signature for " + jar)

  def deleteFromProject(self, projectDir):
    regex = re.compile(self.getArtifactIdAndVersion() + '.*')
    libDir = projectDir + '/libs/'
    for f in os.listdir(libDir):
      if regex.match(f):
        fileToDelete = os.path.join(libDir, f)
        print("Deleting old artifact " + fileToDelete)
        os.remove(fileToDelete)
    libSrcDir = projectDir + '/libs-sources/'
    for f in os.listdir(libSrcDir):
      if regex.match(f):
        fileToDelete = os.path.join(libSrcDir, f)
        print("Deleting old artifact " + fileToDelete)
        os.remove(fileToDelete)

  def verifySignature(self, detachedSigFile, dataFile):
    gpg = gnupg.GPG()
    availableKeys = gpg.list_keys()
    if not any(key['fingerprint'] == self.pgpKeyFingerprint for key in availableKeys):
      longId = self.pgpKeyFingerprint[-16:]
      import_result = gpg.recv_keys('pgp.mit.edu', '0x' + longId)
    with io.open(detachedSigFile, 'rb') as f:
      v = gpg.verify_file(f, dataFile)
      return v.fingerprint == self.pgpKeyFingerprint

  def createDirStructure(self, projectDir):
    # TODO does not need to be instance method
    libSrcDir = projectDir + '/libs-sources/'
    if not os.path.exists(libSrcDir):
      os.makedirs(libSrcDir)
    libDir = projectDir + '/libs/'
    if not os.path.exists(libDir):
      os.makedirs(libDir)


parser = argparse.ArgumentParser()
parser.add_argument("--project", "-p")
parser.add_argument("--file", "-f", nargs='*', help="Optional additional artifact files")

args = parser.parse_args()
args.project = os.path.abspath(args.project)

artifacts = []

projectArtifacts = args.project + "/artifacts.csv"
if os.path.isfile(projectArtifacts):
  with open(projectArtifacts) as f:
    reader = csv.reader(f)
    for row in reader:
      artifacts.append(MavenArtifact(row[0], row[1], row[2], row[3]))

for artifactFile in args.file:
  if os.path.isfile(artifactFile):
    with open(artifactFile) as f:
      reader = csv.reader(f)
      for row in reader:
        artifacts.append(MavenArtifact(row[0], row[1], row[2], row[3]))
  else:
    print("Specified file does not exist")

for a in artifacts:
  a.installIn(args.project)
