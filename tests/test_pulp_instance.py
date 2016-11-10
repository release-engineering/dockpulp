#!/usr/bin/python
# -*- coding: utf-8 -*-


from dockpulp import Pulp, RequestsHttpCaller, errors
import pytest
import hashlib
import json
import requests
import tarfile
from tempfile import NamedTemporaryFile
from textwrap import dedent
from contextlib import nested
from flexmock import flexmock


# fixtures
@pytest.fixture
def pulp(tmpdir):
    with nested(NamedTemporaryFile(mode='wt'), NamedTemporaryFile(mode='wt')) as (fp, df):
        name = 'test'
        fp.write(dedent("""
            [pulps]
            {name} = foo
            [registries]
            {name} = foo
            [filers]
            {name} = foo
            [redirect]
            {name} = no
            [distributors]
            {name} = foo
            [release_order]
            {name} = foo
            [retries]
            {name} = 2
            """).format(name=name))
        fp.flush()

        df.write(dedent("""
            {}
            """))
        df.flush()
        pulp = Pulp(env=name, config_file=fp.name, config_distributors=df.name)
    return pulp


# wrapper classes
class testRead(object):
    def read(self):
        return 'test'


class testResponse(object):
    def __init__(self):
        self.raw = testRead()


class testHash(object):
    def __init__(self, output):
        self.output = output

    def hexdigest(self):
        return self.output


# tests
class TestPulp(object):
    # Tests of methods from Pulp class.
    @pytest.mark.parametrize('cert, key', [('foo', 'bar')])
    def test_set_certs(self, pulp, cert, key):
        pulp.set_certs(cert, key)
        assert pulp.certificate == cert
        assert pulp.key == key

    @pytest.mark.parametrize('tid, url', [
        ('111', '/pulp/api/v2/tasks/111/')
    ])
    def test_getTask(self, pulp, tid, url):
        result = 'task_received'
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .with_args('get', url)
            .once()
            .and_return(result))
        assert pulp.getTask(tid) == result

    @pytest.mark.parametrize('tid, url', [
        ('111', '/pulp/api/v2/tasks/111/')
    ])
    def test_getTaskRetries(self, pulp, tid, url):
        result = 'task_received'
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .with_args('get', url)
            .twice()
            .and_raise(requests.ConnectionError)
            .and_return(result))
        assert pulp.getTask(tid) == result

    @pytest.mark.parametrize('tid, url', [
        ('111', '/pulp/api/v2/tasks/111/')
    ])
    def test_getTaskRetriesFail(self, pulp, tid, url):
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .with_args('get', url)
            .twice()
            .and_raise(requests.ConnectionError))
        with pytest.raises(requests.ConnectionError):
            pulp.getTask(tid)

    def test_getPrefix(self, pulp):
        assert pulp.getPrefix() == 'redhat-'

    @pytest.mark.parametrize('rid, redirect', [
        ('test-repo', 'http://example/url'),
        ('test-repo', 'https://example/url'),
        ('test-repo', 'http://www.example.com/url/foo/bar'),
        ('test-repo', 'https://www.example.com/url/foo/bar')
    ])
    def test_updateRedirect(self, pulp, rid, redirect):
        update = {'redirect-url': redirect}
        blob = []
        did = {'distributor_type_id': 'testdist', 'id': 'test'}
        t = {'state': 'finished'}
        blob.append(did)
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .and_return(blob, '111', t)
            .one_by_one())
        assert pulp.updateRepo(rid, update) is None

    @pytest.mark.parametrize('rid, redirect', [
        ('test-repo', 'test'),
        ('test-repo', 'example/test'),
        ('test-repo', 'https://example')
    ])
    def test_updateRedirectFail(self, pulp, rid, redirect):
        update = {'redirect-url': redirect}
        blob = []
        did = {'distributor_type_id': 'testdist', 'id': 'test'}
        t = {'state': 'finished'}
        blob.append(did)
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .and_return(blob, '111', t)
            .one_by_one())
        with pytest.raises(errors.DockPulpError):
            pulp.updateRepo(rid, update)

    @pytest.mark.parametrize('repos, content, history, label', [
        ('test-repo', True, True, True),
        ('test-repo', False, True, True),
    ])
    def test_listHistory(self, pulp, repos, content, history, label):
        blob = {'notes': {'_repo-type': 'docker-repo'}, 'id': 'testid', 'description': 'testdesc',
                'display_name': 'testdisp', 'distributors': [], 'scratchpad': {}}
        units = [{'unit_type_id': 'docker_manifest',
                  'metadata': {'fs_layers': [{'blob_sum': 'test'}], 'digest': 'testdig',
                               'tag': 'testtag'}},
                 {'unit_type_id': 'docker_image', 'metadata': {'image_id': 'v1idtest'}}]
        labels = {'config': {'Labels': {'label1': 'label2'}}}
        v1Compatibility = {'parent': 'testparent', 'id': 'testid',
                           'config': {'Labels': {'testlab1': 'testlab2'}}}
        data = {'history': [{'v1Compatibility': json.dumps(v1Compatibility)}]}
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .and_return(blob, units, labels, data)
            .one_by_one())
        history = pulp.listRepos(repos, content, history, label)
        for key in history[0]['manifests']:
            assert history[0]['manifests'][key]['v1parent'] == v1Compatibility['parent']
            assert history[0]['manifests'][key]['v1id'] == v1Compatibility['id']
            assert history[0]['manifests'][key]['v1labels']['testlab1'] == \
                v1Compatibility['config']['Labels']['testlab1']
        for key in history[0]['v1_labels']:
            assert history[0]['v1_labels'][key] == labels['config']['Labels']

    @pytest.mark.parametrize('repo, image', [('testrepo', 'testimg')])
    def test_checkLayers(self, pulp, repo, image):
        images = []
        images.append(image)
        req = requests.Response()
        flexmock(
            req,
            raw="rawtest")
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .once()
            .and_return(req))
        flexmock(tarfile)
        (tarfile
            .should_receive('open')
            .once()
            .and_return(tarfile.TarFile))
        flexmock(tarfile.TarFile)
        (tarfile.TarFile
            .should_receive('close')
            .once()
            .and_return())
        response = pulp.checkLayers(repo, images)
        assert not response['error']

    @pytest.mark.parametrize('repo, image', [('testrepo', 'testimg')])
    def test_checkLayersFail(self, pulp, repo, image):
        images = []
        images.append(image)
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .twice()
            .and_raise(requests.exceptions.ConnectionError))
        response = pulp.checkLayers(repo, images)
        assert response['error']

    @pytest.mark.parametrize('repo, blob', [('testrepo', 'testblob')])
    def test_checkBlobs(self, pulp, repo, blob):
        blobs = []
        blobs.append('sha256:%s' % blob)
        req = testResponse()
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .once()
            .and_return(req))
        flexmock(hashlib)
        (hashlib
            .should_receive('sha256')
            .once()
            .and_return(testHash(blob)))
        response = pulp.checkBlobs(repo, blobs)
        assert not response['error']

    @pytest.mark.parametrize('repo, blob', [('testrepo', 'testblob')])
    def test_checkBlobsMismatch(self, pulp, repo, blob):
        blobs = []
        blobs.append('sha256:%s' % blob)
        req = testResponse()
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .once()
            .and_return(req))
        flexmock(hashlib)
        (hashlib
            .should_receive('sha256')
            .once()
            .and_return(testHash('test')))
        response = pulp.checkBlobs(repo, blobs)
        assert response['error']

    @pytest.mark.parametrize('repo, blob', [('testrepo', 'sha256:testblob')])
    def test_checkBlobsFail(self, pulp, repo, blob):
        blobs = []
        blobs.append(blob)
        flexmock(RequestsHttpCaller)
        (RequestsHttpCaller
            .should_receive('__call__')
            .twice()
            .and_raise(requests.exceptions.ConnectionError))
        response = pulp.checkBlobs(repo, blobs)
        assert response['error']
