#!/usr/bin/env python3
import argparse
import urllib.request
import re
import os
import csv
import io
import gnupg
import sys
import shutil
import time

USER_HOME = os.path.expanduser('~')
USER_M2_REPO = USER_HOME + '/.m2/repository/'
SONATYPE_RELEASE_URL = "https://oss.sonatype.org/content/repositories/releases"
SONATYPE_SNAPSHOT_URL = "https://oss.sonatype.org/content/repositories/snapshots"
SNAPSHOT = '-SNAPSHOT'
SOURCES_REGEX = re.compile('".*sources.jar"')
JAR_REGEX = re.compile('".*[0-9].jar"')

httplib2Available = True
try:
    import httplib2
    httplib2CacheDir = USER_HOME + '/.cache/httplib2'
    if not os.path.exists(httplib2CacheDir):
        os.makedirs(httplib2CacheDir)
    h = httplib2.Http(httplib2CacheDir)
except ImportError:
    httplib2Available = False

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
    path = urllib.request.urlopen(url)
    return path.read().decode('utf-8')


class MavenArtifact:
  def __init__(self, groupId, artifactId, version, pgpKeyFingerprint):
    self.groupId = groupId
    self.artifactId = artifactId
    self.version = version
    self.pgpKeyFingerprint = pgpKeyFingerprint
    self.isSnapshot = version.endswith(SNAPSHOT)

    directory = groupId.replace('.', '/')
    self.mavenRepoUrl = '/' + directory + '/' + self.artifactId + '/' + self.version
    if self.isSnapshot:
      self.artifactDirectoryUrl = SONATYPE_SNAPSHOT_URL + self.mavenRepoUrl
      self.artifactIdAndVersion = self.artifactId + '-' + self.version[:-len(SNAPSHOT)]
      self.destFilenamePrefix = self.artifactIdAndVersion + SNAPSHOT
    else:
      self.artifactDirectoryUrl = SONATYPE_RELEASE_URL + self.mavenRepoUrl
      self.artifactIdAndVersion = self.artifactId + '-' + self.version
      self.destFilenamePrefix = self.artifactIdAndVersion

    self.jarDestFilename = self.destFilenamePrefix + '.jar'
    self.jarSigDestFilename = self.jarDestFilename + '.asc'
    self.jarSourceDestFilename = self.destFilenamePrefix + '-sources.jar'

    maybeSnapshot = ""
    if self.isSnapshot:
      maybeSnapshot = SNAPSHOT
    self.localJarUrl = USER_M2_REPO + self.mavenRepoUrl + '/' + self.artifactIdAndVersion + maybeSnapshot + '.jar'
    self.localSourceUrl = USER_M2_REPO + self.mavenRepoUrl + '/' + self.artifactIdAndVersion + maybeSnapshot +  '-sources.jar'
    self.localJarSigUrl = self.localJarUrl + '.asc'
    self.localJarTimestamp = time.gmtime(0)
    if os.path.isfile(self.localJarUrl):
        self.localJarTimestamp = time.gmtime(os.path.getmtime(self.localJarUrl))

  def __str__(self):
    return self.groupId + ':' + self.artifactId + ':' + self.version

  def installIn(self, project):
    jarDest = project.libsDir + self.jarDestFilename
    jarSigDest = project.libsDir + self.jarSigDestFilename
    jarSourceDest = project.libsSourcesDir + self.jarSourceDestFilename
    if os.path.exists(jarDest):
      if self.isSnapshot:
        print("Not fetching " + str(self) + " as SNAPSHOT artifact already exists")
        return
      elif self.verifySignature(jarSigDest, jarDest):
        print("Not fetching " + str(self) + " as artifact already exists and signature is valid")
        return

    # Delete old artifacts
    regex = re.compile(self.artifactId + '.*')
    dirs = [project.libsDir, project.libsSourcesDir]
    for d in dirs:
      for f in os.listdir(d):
        if regex.match(f):
          fileToDelete = os.path.join(d, f)
          print("Deleting old artifact " + fileToDelete)
          os.remove(fileToDelete)

    if not self.isSnapshot:
      remoteJarUrl = self.artifactDirectoryUrl + '/' + self.artifactIdAndVersion + '.jar'
      remoteSourceUrl = self.artifactDirectoryUrl + '/' + self.artifactIdAndVersion + '-sources.jar'
    else:
      print("Looking up remote artifact for " + str(self))
      content = getDirectoryContent(self.artifactDirectoryUrl)
      jars = JAR_REGEX.findall(content)
      jars.sort()
      newestJar = jars[-1]
      remoteJarUrl = newestJar.replace('"', '')
      components = remoteJarUrl.split('/')[-1].split('-')
      timestamp = components[-2]
      identifier = components[-1].split('.')[0]
      remoteJarTimestamp = time.strptime(timestamp, "%Y%m%d.%H%M%S")
      remoteSourceUrl = self.artifactDirectoryUrl + '/' + self.artifactIdAndVersion + '-' + timestamp + '-' + identifier + '-sources.jar'

    remoteJarSigUrl = remoteJarUrl + '.asc'

    # Place in project logic
    # If it's a snapshot and the localJartimestamp is newer then the remove, use the local one.
    # Or use the local one if it's not a snapshot but we have the artifact in the local maven cache
    if ((self.isSnapshot and (self.localJarTimestamp > remoteJarTimestamp)) or (not self.isSnapshot and os.path.isfile(self.localJarUrl))):
      print("Copying " + self.localJarUrl + " to " + project.libsDir)
      shutil.copy(self.localJarUrl, jarDest)
      if not self.isSnapshot:
        print("Copying " + self.localJarSigUrl + " to " + project.libsDir)
        shutil.copy(self.localJarSigUrl, jarSigDest)
      print("Copying " + self.localSourceUrl + " to " + project.libsSourcesDir)
      shutil.copy(self.localSourceUrl, jarSourceDest)
    # Otherwise use the remote (snapshot) artifact
    else:
      print("Downloading " + self.jarDestFilename + " to " + project.libsDir)
      downloadFile(remoteJarUrl, jarDest)
      if not self.isSnapshot:
        print("Downloading " + self.jarSigDestFilename + " to " + project.libsDir)
        downloadFile(remoteJarSigUrl, jarSigDest)
      print("Downloading " + self.jarSourceDestFilename + " to " + project.libsSourcesDir)
      downloadFile(remoteSourceUrl, jarSourceDest)

    if not self.isSnapshot:
      if self.verifySignature(jarSigDest, jarDest):
        print("Successfully verified signature for " + jarDest)
      else:
        raise Exception("Could not verify signature for " + jarDest)

    # create the .properties file
    f = open(jarDest + '.properties', 'w+')
    f.write('src=../libs-sources/' + self.jarSourceDestFilename)
    f.close()

  def verifySignature(self, detachedSigFile, dataFile):
    gpg = gnupg.GPG()
    availableKeys = gpg.list_keys()
    if not any(key['fingerprint'] == self.pgpKeyFingerprint for key in availableKeys):
      longId = self.pgpKeyFingerprint[-16:]
      import_result = gpg.recv_keys('pgp.mit.edu', '0x' + longId)
    with io.open(detachedSigFile, 'rb') as f:
      v = gpg.verify_file(f, dataFile)
      return v.fingerprint == self.pgpKeyFingerprint

class Project:
  def __init__(self, projectDir):
    self.projectDir = projectDir
    self.libsDir = self.projectDir + '/libs/'
    self.libsSourcesDir = self.projectDir + '/libs-sources/'
    if not os.path.exists(self.libsDir):
      os.makedirs(self.libsDir)
    if not os.path.exists(self.libsSourcesDir):
      os.makedirs(self.libsSourcesDir)

def processArtifactsFile(artifactsFile, artifacts):
    versionVariables = {}
    csvLines = []
    with open(artifactsFile) as f:
        for line in f:
            if '=' in line:
                versionVariableLine = line.split('=', 1)
                versionVariables[versionVariableLine[0]] = versionVariableLine[1].rstrip()
            else:
                csvLines.append(line)
        reader = csv.reader(csvLines)
        for row in reader:
            groupId = row[0]
            artifactId = row[1]
            pgpKeyFingerprint = row[3]
            if row[2][0] == '$':
                version = versionVariables[row[2][1:]]
            else:
                version = row[2]
            artifacts.append(MavenArtifact(groupId, artifactId, version, pgpKeyFingerprint))


parser = argparse.ArgumentParser()
parser.add_argument("--project", "-p")
parser.add_argument("--file", "-f", nargs='*', help="Optional additional artifact files")

args = parser.parse_args()
args.project = os.path.abspath(args.project)

project = Project(args.project)
artifacts = []

projectArtifacts = args.project + "/artifacts.csv"
if os.path.isfile(projectArtifacts):
  processArtifactsFile(projectArtifacts, artifacts)

for artifactFile in args.file:
  if os.path.isfile(artifactFile):
      processArtifactsFile(artifactFile, artifacts)
  else:
    print("Specified file does not exist")

for a in artifacts:
  a.installIn(project)
