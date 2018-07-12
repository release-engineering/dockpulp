#!/usr/bin/python
# -*- coding: utf-8 -*-


from dockpulp import imgutils
import pytest
import tarfile
import os
from io import BytesIO


class TarWriter(object):
    def __init__(self, outfile, directory=None):
        mode = "w|bz2"
        if hasattr(outfile, "write"):
            self.tarfile = tarfile.open(fileobj=outfile, mode=mode)
        else:
            self.tarfile = tarfile.open(name=outfile, mode=mode)
        self.directory = directory or ""

    def __enter__(self):
        """Open Tarfile."""
        return self

    def __exit__(self, typ, val, tb):
        """Close Tarfile."""
        self.tarfile.close()

    def write_file(self, name, content):
        buf = BytesIO(content)
        arcname = os.path.join(self.directory, name)

        ti = tarfile.TarInfo(arcname)
        ti.size = len(content)
        self.tarfile.addfile(ti, fileobj=buf)


# tests
class TestImgutils(object):
    # Tests of methods from imgutils
    @pytest.mark.parametrize('path', ['repositories', './repositories', ''])
    @pytest.mark.parametrize('tarjson',
                             ['{"foo": "test1", "bar": "test2"}',
                              '{"bar":{"test2": "a", "test3": "b"}}',
                              '{"bar":{"test2": "testmember", "test3": "testmember"}}'])
    def test_check_repo(self, tmpdir, path, tarjson):
        filename = str(tmpdir.join("archive.tar"))

        with TarWriter(filename, directory='test/dir') as t:
            t.write_file(path, str.encode(tarjson))
            t.write_file('testmember', str.encode('testdata'))

        if path == '':
            assert imgutils.check_repo(filename) == 1
        elif tarjson == '{"foo": "test1", "bar": "test2"}':
            assert imgutils.check_repo(filename) == 2
        elif tarjson == '{"bar":{"test2": "a", "test3": "b"}}':
            assert imgutils.check_repo(filename) == 3
        else:
            assert imgutils.check_repo(filename) == 0
