#!/usr/bin/python
# -*- coding: utf-8 -*-


from dockpulp import Pulp, cli
import pytest
import os
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

    def createRepo():
        return

    def getAncestors(self, arg):
        return arg


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

    @pytest.mark.parametrize('lib', [True, False])
    @pytest.mark.parametrize('args', ['1 2 3', '1 2',
                                      'test /content/test', 'foo bar /content/foo/bar'])
    def test_do_create(self, args, lib):
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
        flexmock(testPulp)
        (testPulp
            .should_receive('isRedirect')
            .and_return(True))
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
