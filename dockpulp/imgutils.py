# This file is part of dockpulp.
#
# dockpulp is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# dockpulp is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with dockpulp.  If not, see <http://www.gnu.org/licenses/>.

import contextlib
import os
import tarfile

try:
    # Python 2.6 and earlier
    import simplejson as json
except ImportError:
    import sys
    if sys.version_info[0] > 2 or sys.version_info[1] > 6:
        import json
    else:
        # json on python 2.6 does not behave like simplejson
        raise

# see https://github.com/pulp/pulp_docker/blob/master/common/pulp_docker/common/tarutils.py


def get_manifest(tarfile_path):
    """Extract and return manifest in tarball.

    Given a path to a tarfile, which is itself the product of "docker save",
    this discovers the manifest for the collection of images, which provides
    version information.
    """
    manifest = []
    configjson = None
    with contextlib.closing(tarfile.open(tarfile_path)) as archive:
        for member in archive.getmembers():
            # find the "manifest.json" file, which points to metadata json file
            if os.path.basename(member.path) == 'manifest.json':
                initial_manifest = json.load(archive.extractfile(member))
                configjson = initial_manifest[0]['Config']
        for member in archive.getmembers():
            # get manifest from shasum json file, docker ver > 1.10
            if configjson and os.path.basename(member.path) == configjson:
                image_data = json.load(archive.extractfile(member))
                manifest.append(image_data)
            # find the "json" files, which contain all image metadata
            # legacy code for docker ver < 1.10
            elif not configjson and os.path.basename(member.path) == 'json':
                image_data = json.load(archive.extractfile(member))
                manifest.append(image_data)
    return manifest


def get_metadata(tarfile_path):
    """Extract and return metadata in tarball.

    Given a path to a tarfile, which is itself the product of "docker save",
    this discovers what images (layers) exist in the archive and returns
    metadata about each.
    """
    metadata = []
    with contextlib.closing(tarfile.open(tarfile_path)) as archive:
        for member in archive.getmembers():
            # find the "json" files, which contain all image metadata
            if os.path.basename(member.path) == 'json':
                image_data = json.load(archive.extractfile(member))
                metadata.append(image_data)
    return metadata


def get_metadata_pulp(md):
    """Go through read metadata and figure out parents, IDs, and sizes.

    Current fields in metadata:
        parent: ID of the parent image, or None if there is none
        size:   size in bytes as reported by docker
    """
    details = {}
    # At some point between docker 0.10 and 1.0, it changed behavior
    # of whether these keys are capitalized or not.
    for image_data in md:
        image_id = image_data.get('id', image_data.get('Id'))
        details[image_id] = {
            'parent': image_data.get('parent', image_data.get('Parent')),
            'size': image_data.get('size', image_data.get('Size'))
        }
    return details


def get_versions(md):
    """Return a dict of image-IDs to versions.

    Inspect the docker version used with the construction of each layer in
    an image.
    """
    vers = {}
    for data in md:
        image_id = data.get('id', data.get('Id'))
        if 'docker_version' in data:
            vers[image_id] = data['docker_version']
    return vers


def check_repo(tarfile_path):
    """Confirm the image has a "repositories" file where it should.

    The return code indicates the results of the check.
    0 - repositories file is good, it passes the check
    1 - repositories file is missing
    2 - more than 1 repository is defined in the file, pulp requires 1
    3 - repositories file references image IDs not in the tarball itself
    """
    found = False
    repo_data = None
    seen_ids = []
    with contextlib.closing(tarfile.open(tarfile_path)) as archive:
        for member in archive.getmembers():
            # member.path can be: "repositories" or "./repositories"
            if os.path.basename(member.path) == "repositories":
                repo_data = json.load(archive.extractfile(member))
                found = True
                if len(repo_data) != 1:
                    return 2
            else:
                seen_ids.append(os.path.basename(member.path))
    if found is False:
        return 1
    val = repo_data.popitem()[1]  # don't care about repo name at all
    for ver, iid in val.items():
        if iid not in seen_ids:
            return 3
    return 0


def _get_hops(iid, md, hops=0):
    """Return how many parents (layers) an image has."""
    par = md[iid].get('parent', None)
    if par is not None:
        return _get_hops(par, md, hops=hops + 1)
    else:
        return hops


def get_id(tarfile_path):
    """Return the ID for this particular image.

    Ignores heritage and children.
    """
    meta_raw = get_metadata(tarfile_path)
    metadata = get_metadata_pulp(meta_raw)
    return get_top_layer(metadata)


# not used, might be useful later
def get_ancestry(image_id, metadata):
    """Calculate and return ancestry list for image.

    Given an image ID and metadata about each image, this calculates and returns
    the ancestry list for that image. It walks the "parent" relationship in the
    metadata to assemble the list, which is ordered with the child leaf at the
    top.
    """
    image_ids = []
    while image_id:
        image_ids.append(image_id)
        image_id = metadata[image_id].get('parent')
    return tuple(image_ids)


def get_top_layer(pulp_md):
    """Find the top (youngest) layer."""
    # Find layers that are parents
    layers = set()
    parents = set()
    for img_hash, value in pulp_md.items():
        layers.add(img_hash)
        if 'parent' in value:
            parents.add(value['parent'])
        else:
            # Base layer has no 'parent' but it itself a parent
            parents.add(img_hash)

    # Any layers not parents are the youngest.
    return list(layers - parents)[0]
