#!/usr/bin/python
# -*- coding: utf-8 -*-


from dockpulp import Pulp, cli
import pytest
import os
import json
import logging
from flexmock import flexmock


# wrapper classes
class testbOpts(object):
    def __init__(self, server="testserv", config_file="testconf",
                 debug=False, cert=True, key=True):
        self.server = server
        self.config_file = config_file
        self.debug = debug
        self.cert = cert
        self.key = key


class testPulp(object):
    def __init__(self):
        self.certificate = None
        self.key = None
        self.AUTH_CER_FILE = ''
        self.AUTH_KEY_FILE = ''

    def set_certs(self, cert, key):
        return

    def setDebug():
        return

    def isRedirect():
        return

    def createRepo(self, arg1, arg2, desc=None, title=None,
                   protected=None, productline=None, library=None,
                   distribution=None, prefix_with=None, rel_url=None):
        return

    def getAncestors(self, arg):
        return arg

    def getPrefix(self):
        return

    def getSigstore(self):
        return 'SIGSTORE'

    def associate(self, arg1, arg2):
        return {'id': 0}

    def copy(self, arg1, arg2):
        return

    def listRepos(self, repos=None, content=None, history=None, labels=None):
        return

    def updateRepo(self, arg1, arg2):
        return

    def deleteRepo(self, arg1, arg2):
        return

    def emptyRepo(self, arg1):
        return


# tests
class TestCLI(object):
    # Tests of methods from CLI
    @pytest.mark.parametrize('debug', [True, False])
    @pytest.mark.parametrize('error', [True, False])
    @pytest.mark.parametrize('cert, key',
                             [(None, True), (True, None),
                              (True, True), (None, None)])
    def test_pulp_login(self, debug, cert, key, error):
        bopts = testbOpts("testserv", "testconf", debug, cert, key)
        p = testPulp()
        (flexmock(Pulp)
            .new_instances(p)
            .with_args(Pulp, env=bopts.server, config_file=bopts.config_file))
        if debug:
            flexmock(testPulp)
            (testPulp
                .should_receive('setDebug')
                .once()
                .and_return(None))
        flexmock(os.path)
        if error and not (key or cert):
            (os.path
                .should_receive('exists')
                .once()
                .and_return(False))
            with pytest.raises(SystemExit):
                cli.pulp_login(bopts)
            return
        elif not cert or not key:
            (os.path
                .should_receive('exists')
                .twice()
                .and_return(True))
        assert cli.pulp_login(bopts) is p

    @pytest.mark.parametrize('bargs', ['1', '1 2'])
    def test_do_ancestry(self, bargs):
        bargs = bargs.split(" ")
        bopts = testbOpts()
        p = testPulp()
        (flexmock(Pulp)
            .new_instances(p)
            .with_args(Pulp, env=bopts.server, config_file=bopts.config_file))
        if len(bargs) != 1:
            with pytest.raises(SystemExit):
                cli.do_ancestry(bopts, bargs)
        else:
            assert cli.do_ancestry(bopts, bargs) is None

    @pytest.mark.parametrize('bargs', ['1', '1 2'])
    def test_do_associate(self, bargs):
        bargs = bargs.split(" ")
        bopts = testbOpts()
        p = testPulp()
        (flexmock(Pulp)
            .new_instances(p)
            .with_args(Pulp, env=bopts.server, config_file=bopts.config_file))
        if len(bargs) != 2:
            with pytest.raises(SystemExit):
                cli.do_associate(bopts, bargs)
        else:
            assert cli.do_associate(bopts, bargs) is None

    @pytest.mark.parametrize('lib', [True, False])
    @pytest.mark.parametrize('img', [True, False])
    @pytest.mark.parametrize('manifest', [True, False])
    @pytest.mark.parametrize('noprefix', [True, False])
    @pytest.mark.parametrize('args', ['1 2 3', '1 2', '1'])
    def test_do_clone(self, args, lib, img, manifest, noprefix):
        bopts = testbOpts()
        p = testPulp()
        if img:
            images = {'1': '1'}
        else:
            images = {}
        if manifest:
            manifests = {'2': '2'}
        else:
            manifests = {}

        oldinfo = [{'redirect': None, 'description': None, 'title': None,
                    'protected': "False", "images": images, "manifests": manifests}]
        (flexmock(Pulp)
            .new_instances(p)
            .once()
            .with_args(Pulp, env=bopts.server, config_file=bopts.config_file))
        args = args.split(" ")
        bargs = args[:]
        if lib:
            bargs.append('-l')
        if noprefix:
            bargs.append('--noprefix')
        if lib and len(args) != 2:
            with pytest.raises(SystemExit):
                cli.do_clone(bopts, bargs)
        elif not lib and len(args) != 3:
            with pytest.raises(SystemExit):
                cli.do_clone(bopts, bargs)
        else:
            if lib:
                if noprefix:
                    repoid = '%s' % args[1]
                else:
                    repoid = 'redhat-%s' % args[1]
                productid = None
            else:
                if noprefix:
                    repoid = '%s-%s' % (args[1], args[2])
                else:
                    repoid = 'redhat-%s-%s' % (args[1], args[2])
                productid = args[1]
            if noprefix:
                prefix_with = ''
            else:
                prefix_with = 'redhat-'
            tags = {'tag': '1:1'}
            flexmock(testPulp)
            if not noprefix:
                (testPulp
                    .should_receive('getPrefix')
                    .once()
                    .and_return('redhat-'))
            (testPulp
                .should_receive('listRepos')
                .once()
                .with_args(args[0], content=True)
                .and_return(oldinfo))
            (testPulp
                .should_receive('createRepo')
                .once()
                .with_args(repoid, None, desc=None, title=None, protected=False,
                           productline=productid, distribution=None, prefix_with=prefix_with)
                .and_return(None))
            if img:
                (testPulp
                    .should_receive('copy')
                    .once()
                    .with_args(repoid, '1')
                    .and_return(None))
                (testPulp
                    .should_receive('updateRepo')
                    .once()
                    .with_args(repoid, tags)
                    .and_return(None))
            if manifest:
                (testPulp
                    .should_receive('copy')
                    .once()
                    .with_args(repoid, '2')
                    .and_return(None))
            assert cli.do_clone(bopts, bargs) is None

    @pytest.mark.parametrize('lib', [True, False])
    @pytest.mark.parametrize('noprefix', [True, False])
    @pytest.mark.parametrize('args', ['1 2 3', '1 2',
                                      'test /content/test', 'foo bar /content/foo/bar'])
    def test_do_create(self, args, lib, noprefix):
        bopts = testbOpts()
        p = testPulp()
        (flexmock(Pulp)
            .new_instances(p)
            .once()
            .with_args(Pulp, env=bopts.server, config_file=bopts.config_file))
        args = args.split(" ")
        bargs = args[:]
        if lib:
            bargs.append('-l')
        if noprefix:
            bargs.append('--noprefix')
        flexmock(testPulp)
        if not noprefix:
            (testPulp
                .should_receive('getPrefix')
                .once()
                .and_return('redhat-'))
        (testPulp
            .should_receive('isRedirect')
            .and_return(True))
        if not lib and noprefix and args[-1].startswith('/content') and args[0] == 'foo':
            (testPulp
                .should_receive('createRepo')
                .with_args('foo-bar', '/content/foo/bar', library=lib, protected=False, title=None,
                           productline='foo', distribution=None, desc="No description",
                           prefix_with='', rel_url='content/foo/bar')
                .and_return(None))
        else:
            (testPulp
                .should_receive('createRepo')
                .and_return(None))
        if lib and len(args) != 2:
            with pytest.raises(SystemExit):
                cli.do_create(bopts, bargs)
        elif not lib and len(args) != 3:
            with pytest.raises(SystemExit):
                cli.do_create(bopts, bargs)
        elif not args[-1].startswith('/content'):
            with pytest.raises(SystemExit):
                cli.do_create(bopts, bargs)
        else:
            assert cli.do_create(bopts, bargs) is None

    @pytest.mark.parametrize('bargs', ['1', None])
    def test_do_delete(self, bargs):
        if bargs is not None:
            bargs = bargs.split(" ")
        bopts = testbOpts()
        p = testPulp()
        (flexmock(Pulp)
            .new_instances(p)
            .with_args(Pulp, env=bopts.server, config_file=bopts.config_file))
        if bargs is None:
            with pytest.raises(SystemExit):
                cli.do_delete(bopts, bargs)
        else:
            (flexmock(testPulp)
                .should_receive('listRepos')
                .with_args(bargs[0], content=True)
                .once()
                .and_return([{'images': {}, 'manifests': {}}]))
            assert cli.do_delete(bopts, bargs) is None

    @pytest.mark.parametrize('bargs', ['1', None])
    def test_do_empty(self, bargs):
        if bargs is not None:
            bargs = bargs.split(" ")
        bopts = testbOpts()
        p = testPulp()
        (flexmock(Pulp)
            .new_instances(p)
            .with_args(Pulp, env=bopts.server, config_file=bopts.config_file))
        if bargs is None:
            with pytest.raises(SystemExit):
                cli.do_empty(bopts, bargs)
        else:
            assert cli.do_empty(bopts, bargs) is None

    @pytest.mark.parametrize('silent', [True, False])
    def test_do_list(self, caplog, silent):
        bopts = testbOpts()
        bargs = ['test-repo', '--content', '--details', '--labels', '--lists']
        if silent:
            bargs.append('--silent')
        p = testPulp()
        (flexmock(Pulp)
            .new_instances(p)
            .with_args(Pulp, env=bopts.server, config_file=bopts.config_file))
        repos = [{'id': 'test-repo', 'detail': 'foobar',
                  'images': {'testimage': ['testtag']},
                  'v1_labels': {'testimage': {'testkey': 'testval'}},
                  'manifests': {'testmanifest': {'layers': ['testlayer1'], 'tag': 'testtag',
                                                 'config': 'testconfig', 'schema_version': 'testsv',
                                                 'v1id': 'testv1id', 'v1parent': 'testv1parent',
                                                 'v1labels': 'testv1labels'}},
                  'manifest_lists': {'testmanifestlist': {'mdigests': ['testmanifest'],
                                                          'tags': ['testtag']}},
                  'tags': {'testtag': 'testmanifest'}}]

        (flexmock(testPulp)
            .should_receive('listRepos')
            .with_args(repos=[bargs[0]], content=True, history=True, labels=True)
            .and_return(repos))

        caplog.setLevel(logging.INFO, logger="dockpulp")
        response = cli.do_list(bopts, bargs)
        if silent:
            output = caplog.text()
            jsontext = output[output.find('['):]
            assert json.loads(jsontext) == repos
        else:
            assert response is None

    def test_print_manifest_metadata(self):
        manifest = 'testmanifest'
        tag = 'testtag'
        output = {manifest:
                  {'tag': tag,
                   'active': ' (active)',
                   'config': 'testconfig',
                   'schema_version': 'testsv'}}

        assert cli._print_manifest_metadata(output, manifest, True) == tag

    @pytest.mark.parametrize('bargs', ['test-repo -r /contentdist', None])
    def test_do_update(self, bargs):
        if bargs is not None:
            bargs = bargs.split(" ")
        bopts = testbOpts()
        p = testPulp()
        (flexmock(Pulp)
            .new_instances(p)
            .with_args(Pulp, env=bopts.server, config_file=bopts.config_file))
        if bargs is None:
            with pytest.raises(SystemExit):
                cli.do_update(bopts, bargs)
        else:
            assert cli.do_update(bopts, bargs) is None
