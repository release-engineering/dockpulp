[![Build Status](https://travis-ci.org/release-engineering/dockpulp.svg?branch=master)](https://travis-ci.org/release-engineering/dockpulp)

# dockpulp
ReST API Client to Pulp for manipulating docker images

NOTE: dockpulp has been decommissioned and this repository has been archived

## Installation

The only test installation is via RPM deployment, which presently is not
integrated with the repository you just checked out. 
You will need to install tito and then run following command for building rpm 
package.

`$ tito build --offline --rpm`

Deployment will leave a file called /etc/dockpulp.conf, which how you configure
the client for use with your Pulp, Crane, and CDN deployments. Read the
comments in that file and make changes as necessary.

## Use

dockpulp provides one command line tool that has several subcommands built into
it. The command is **dock-pulp**. You must log into Pulp before any of the other
commands will be useful. You do not need to be root for these commands; that is
discouraged.

`$ dock-pulp login [-u username] -p password`

This will store a certificate and key pair in your ~/.pulp directory. For the
next 7 days (or whatever the Pulp server is configured for) you will be able to
run future dock-pulp commands without a username or password. When it expires
(or you see a lot of 403s) just run it again. These pairs are
environment-specific.

The default environment is **qa**. If you need to work in a different one, pass
the **--server** option, which comes before the subcommand:

`$ dock-pulp --server prod login [-u username] -p password`

If you run dock-pulp by itself you will get an overview of all of the
subcommands. Each subcommand supports a **--help** option that explains options
to the subcommands. The changes you make could be copying an image from one
repo to another, deleting a repo, uploading an image, tagging them, creating a
new repository or updating the metadata of an existing one. Once all of your
changes are done though, the last command you will run to make them live will
be something like this:

`$ dock-pulp release`

This will tell Pulp to publish configuration details to Crane, making them live
for the environment you are working with. If you uploaded images to Pulp, you
still need to put them in the corresponding CDN environment in their
newly-imported format.

## Examples

List all repositories and the images they contain

`$ dock-pulp list -c`

Tag an image with a few tags. This will override any existing tags for that
image.

`$ dock-pulp tag redhat-rhel6-rhel abc123 latest,6.6-5`

Upload an image

`$ dock-pulp upload some-image.tar.gz redhat-rhel7-rhel`

If you ever need to troubleshoot or investigate a bug, use the --debug option,
which comes before the subcommand. You will see the interactions with the Pulp
REST API.

`$ dock-pulp --debug update --description 'RHEL 7 Images'`

## Other Commands

dockpulp also provides **dock-pulp-bootstrap** and **dock-pulp-restore** which
are special case commands few should have access to or need. The first creates
a **redhat-everything** repository, which is where all uploads are kept. That
way if anyone accidentally deletes an image, it can easily be restored from that
repository, much like a recycle bin. The restore command is used in conjunction
with the **json** subcommand from dock-pulp, which facilitates "cloning" the
configuration of one Pulp-Crane stack in an environment to another.

