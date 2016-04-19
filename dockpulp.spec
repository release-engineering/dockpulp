Name:		dockpulp
Version:	1.19
Release:	1%{?dist}
Summary:	Configure the Pulp instances that power Docker registrires for Red Hat

Group:		Applications/System
License:	Red Hat Internal
URL:		https://github.com/release-engineering/dockpulp.git
Source0:	%{name}-%{version}.tar.gz
BuildRoot:	%(mktemp -ud %{_tmppath}/%{name}-%{version}-%{release}-XXXXXX)
BuildArch:  noarch

BuildRequires:	python-devel
Requires: python-requests
%if 0%{?rhel} == 6
Requires: python-simplejson
%endif

%description
dockpulp provides a client tool that captures configuration conventions
and workflows that are specific to docker image and registries.


%prep
%setup -q

%build

%install
rm -rf $RPM_BUILD_ROOT
install -d $RPM_BUILD_ROOT%{python_sitelib}/dockpulp
install -d $RPM_BUILD_ROOT%{_bindir}
install -pm 0644 dockpulp/* $RPM_BUILD_ROOT%{python_sitelib}/dockpulp
install -pm 0755 bin/dock-pulp.py $RPM_BUILD_ROOT%{_bindir}/dock-pulp
install -pm 0755 bin/dock-pulp-bootstrap.py $RPM_BUILD_ROOT%{_bindir}/dock-pulp-bootstrap
install -pm 0755 bin/dock-pulp-restore.py $RPM_BUILD_ROOT%{_bindir}/dock-pulp-restore


%clean
rm -rf $RPM_BUILD_ROOT


%files
%defattr(-,root,root,-)
%{python_sitelib}/*
%{_bindir}/*
%doc LICENSE


%changelog
* Tue Apr 19 2016 Brendan Reilly <breilly@redhat.com> 1.19-1
- Added extra error check for timeout (breilly@redhat.com)
- Return of a list of uploaded imageids (vrutkovs@redhat.com)

* Tue Mar 29 2016 Brendan Reilly <breilly@redhat.com> 1.18-2
- Bumping version (breilly@redhat.com)
- Protected bit on repos can now be set (breilly@redhat.com)

* Wed Mar 16 2016 Brendan Reilly <breilly@redhat.com> 1.17-2
- Made timeout on pulp waits configurable, new default is 180s
  (breilly@redhat.com)

* Tue Mar 15 2016 Brendan Reilly <breilly@redhat.com> 1.16-2
- dockpulp confirm now checks all parent images (breilly@redhat.com)
- syncRepo: don't change the sync environment (#47) (twaugh@redhat.com)

* Thu Mar 10 2016 Brendan Reilly <breilly@redhat.com> 1.15-2
- bumped version (breilly@redhat.com)
- Fixed broken backwards compat for createRepo api (breilly@redhat.com)
- Fixed bug when releasing more than one repo (breilly@redhat.com)

* Tue Mar 08 2016 Brendan Reilly <breilly@redhat.com> 1.14-3
- Removed dockpulp conf from rpm (breilly@redhat.com)

* Mon Mar 07 2016 Brendan Reilly <breilly@redhat.com> 1.14-2
- Updated distributor conf to work with publish, list, update correctly
  (breilly@redhat.com)
- Bumping version (breilly@redhat.com)
- Adding default distributors file (breilly@redhat.com)
- Can now specify distributors via /etc/dockpulp.conf. Distributors should be
  defined in /etc/dockpulpdistributors.json (breilly@redhat.com)

* Wed Mar 02 2016 Brendan Reilly <breilly@redhat.com> 1.12-11
- Fixed indentation error (breilly@redhat.com)

* Wed Mar 02 2016 Brendan Reilly <breilly@redhat.com> 1.12-10
- Bumped release to 1.12 (breilly@redhat.com)
- Added error check for missing ancestors (breilly@redhat.com)
- Chunk size for uploads is now configurable. Default is 1MB.
  (breilly@redhat.com)
- Now pulls version information correctly from docker 1.10+ images
  (breilly@redhat.com)
- dockpulp create a-b c-d now correctly generates a-b/c-d docker id. Clone args
  changed to reflect createrepo changes (breilly@redhat.com)
- Delete now displays removed layers (breilly@redhat.com)
- Updated to use python from env. (breilly@redhat.com)
- Updated logging to only appear with CLI. (breilly@redhat.com)
- Merge pull request #42 from pbabinca/install-requires-fix
  (breilly@redhat.com)
- Merge pull request #41 from pbabinca/continue-with-no-distributors
  (breilly@redhat.com)
- Sync uses crane instead of pulp. (breilly@redhat.com)
- Include request in install_requires of setup.py (pbabinca@redhat.com)
- Continue if there is no distributor for a repo (pbabinca@redhat.com)
- Sync now copies new images to redhat-everything after sync. Errors should now
  return standard error codes. (breilly@redhat.com)

* Wed Feb 10 2016 Brendan Reilly <breilly@redhat.com> 1.12-9
- Updated confirm and list to work with repos with no redirect-url
  (breilly@redhat.com)
- Updated changes to work correctly with confirm and list (breilly@redhat.com)
- Made redirect-url requirement configurable, as per APPINFRAT-1381
  (breilly@redhat.com)
- Merge pull request #38 from twaugh/sync-port (breilly@redhat.com)
- Don't override the default port (twaugh@redhat.com)
- Don't traceback on incomplete distributor config (twaugh@redhat.com)

* Tue Nov 24 2015 Unknown name <breilly@redhat.com> 1.12-8
- Updated logging to work with python 2.6 (breilly@redhat.com)

* Tue Nov 24 2015 Unknown name <breilly@redhat.com> 1.12-7
- 

* Tue Nov 24 2015 Unknown name <breilly@redhat.com> 1.12-6
- Removed push_to_pulp functions (breilly@redhat.com)
- don't tback when server is not specified (ttomecek@redhat.com)

* Thu Nov 12 2015 Unknown name <breilly@redhat.com> 1.12-5
- Had to add verify to kwargs (breilly@redhat.com)

* Thu Nov 12 2015 Unknown name <breilly@redhat.com> 1.12-4
- merging internal and master branches (breilly@redhat.com)
- Merge pull request #30 from twaugh/syncenv-fix (breilly@redhat.com)
- Merge pull request #29 from twaugh/syncRepo-port (breilly@redhat.com)
- Merge pull request #28 from twaugh/syncRepo-prefix (breilly@redhat.com)
- syncRepo: don't enforce a particular port but have a default
  (twaugh@redhat.com)
- Fix initialization of syncenv instance variable (twaugh@redhat.com)
- syncRepo: enforce prefix (twaugh@redhat.com)
- Fix listRepos() str-to-list conversion (twaugh@redhat.com)
- Merge pull request #25 from mmilata/watch_tasks_fail_early
  (breilly@redhat.com)
- Fix some comments/strings, remove watch_tasks_orig (mmilata@redhat.com)
- - raise exception if any of watched tasks failed (jluza@redhat.com)
- - added deleteTask, copy-paste issue fixed (jluza@redhat.com)
- - better task_watch (jluza@redhat.com)
- - "certificates" in configuration and config_override (jluza@redhat.com)
- Factor out repo search into getRepos (mmilata@redhat.com)
- Added sync function (breilly@redhat.com)
- Added sync function (breilly@redhat.com)
- Don't use logging.basicConfig, set handler to the logger instance
  (bkabrda@redhat.com)
- Fix push_to_pulp with a repo_prefix (mmilata@srck.net)
- Import sys before checking sys.version_info (twaugh@redhat.com)
- Require simplejson on Python 2.6 (twaugh@redhat.com)
- Add simplejson as a requirement for Python 2.6 (twaugh@redhat.com)
- Don't install dockpulp.conf in /etc (twaugh@redhat.com)
- Merge branch 'master' of https://github.com/release-engineering/dockpulp into
  push_to_pulp_perf (jluza@redhat.com)
- - added _error method to RequestsHttpCaller (jluza@redhat.com)
- - faster calling of publish request. Lot of time was spent waiting for http
  response. Requests are now made in parallel what could save time spent on
  waiting for response. (jluza@redhat.com)
- - watch_tasks: moved condition to end of cycle (jluza@redhat.com)
- - typo fix (jluza@redhat.com)
- Automatic commit of package [dockpulp] minor release [1.11-2].
  (jgregusk@redhat.com)
- fix missing initialization (jgregusk@redhat.com)
- Automatic commit of package [dockpulp] minor release [1.11-1].
  (jgregusk@redhat.com)
- - repo_name policy in push_to_pulp (jluza@redhat.com)
- fix upstream URL (jgregusk@redhat.com)
- add dockpulp.spec (jgregusk@redhat.com)
- omit spec from gitignore (jgregusk@redhat.com)
- add searchRepos support globs for some commands (jgregusk@redhat.com)
- remove obsolete product line check (jgregusk@redhat.com)
- remove tags on older images when tagging a new image (jgregusk@redhat.com)
- add exists() (jgregusk@redhat.com)
- steal ownership in setup.py, include other scripts (jgregusk@redhat.com)
- introduce get_top_layer for atomic-reactor (jgregusk@redhat.com)
- - watch_tasks fixed (jluza@redhat.com)
- use default config path instead of None (ttomecek@redhat.com)
- - added watch_tasks, getTasks method for better performance - added wait=True
  to crane() for better performance (jluza@redhat.com)
- add setup.py (jgregusk@redhat.com)
- Merge pull request #6 from midnightercz/createRepo (jgregusk@redhat.com)
- Merge pull request #4 from pbabinca/configurable-config-file
  (jgregusk@redhat.com)
- Merge pull request #3 from pbabinca/mkdir-typo-fix (jgregusk@redhat.com)
- push_tar_to_pulp: prefix repo names with 'redhat-' (ttomecek@redhat.com)
- prefix all new repos with 'redhat-' (ttomecek@redhat.com)
- createRepo: don't validate registry_id when it's specified
  (ttomecek@redhat.com)
- create repo: enable specifying registry-id (ttomecek@redhat.com)
- compare paths more sanely (ttomecek@redhat.com)
- - fixed: tags duplicates. Conflict tags from already existing images_ids are
  now removed and added to images which are about to be added
  (jluza@redhat.com)
- - fixed cli to match library call (jluza@redhat.com)
- Fix get_top_layer(). (twaugh@redhat.com)
- create repo: enable specifying registry-id (ttomecek@redhat.com)
- Fixed imgutils.get_top_layer(). (twaugh@redhat.com)
- push_to_pulp: use mapping between repos and tags (ttomecek@redhat.com)
- added optional desc and title for new repo in push_to_pulp action
  (jluza@redhat.com)
- new push_tar_to_pulp method and push_to_pulp cmd action (jluza@redhat.com)
- Leave logger setup of the library on the clients (pbabinca@redhat.com)
- Fix mkdir typo in code which created ~/.pulp dir (pbabinca@redhat.com)

* Fri Sep 04 2015 Jay Greguske <jgregusk@redhat.com> 1.12-3
- only warn about ssl once (jgregusk@redhat.com)

* Fri Sep 04 2015 Jay Greguske <jgregusk@redhat.com> 1.12-2
- expose ssl verification (jgregusk@redhat.com)

* Fri Sep 04 2015 Jay Greguske <jgregusk@redhat.com> 1.12-1
- update to 1.12 (jgregusk@redhat.com)
- Don't use logging.basicConfig, set handler to the logger instance
- Import sys before checking sys.version_info
- Require simplejson on Python 2.6 (twaugh@redhat.com)
- Add simplejson as a requirement for Python 2.6
- Don't install dockpulp.conf in /etc (twaugh@redhat.com)
- fix missing initialization
- fix upstream URL
- add dockpulp.spec
- omit spec from gitignore
- add searchRepos support globs for some commands
- remove obsolete product line check
- remove older tags when tagging a new image
- implement exists
- steal ownership in setup.py, include other scripts
- introduce get_top_layer for atomic-reactor
- use default config path instead of None
- add setup.py

* Thu Jun 25 2015 Jay Greguske <jgregusk@redhat.com> 1.11-2
- fix missing initialization (jgregusk@redhat.com)

* Thu Jun 25 2015 Jay Greguske <jgregusk@redhat.com> 1.11-1
- add glob support for some commands
- add exists() and searchRepos() to the API
- add get_top_layer() for atomic-reactor
- update setup.py

* Thu May 28 2015 Jay Greguske <jgregusk@redhat.com> 1.10-2
- fix config extension

* Thu May 28 2015 Jay Greguske <jgregusk@redhat.com> 1.10-1
- move rcm-dockpulp.conf to dockpulp.conf
- bump to 1.10
- add license file
- add sample config file
- set minimum timeout for uploads
- split out environments to a config file
- fix imports for python 2.7 and later

* Fri May 15 2015 Jay Greguske <jgregusk@redhat.com> 1.9-1
- add rhel7 releaser
- version 1.9
- add -C and -K
- support "brew" environment
- remove confirm from spec file
- remove dock-pulp-confirm.py
- add confirm command

* Thu Apr 23 2015 Jay Greguske <jgregusk@redhat.com> 1.8-3
- correct imgutils.get_id

* Thu Apr 16 2015 Jay Greguske <jgregusk@redhat.com> 1.8-2
- minor logging enhancements
- fix usage for do_release

* Thu Apr 02 2015 Jay Greguske <jgregusk@redhat.com> 1.8-1
- on to 1.8
- remove unneeded layers when removing an image
- implement ancestry command

* Mon Mar 16 2015 Jay Greguske <jgregusk@redhat.com> 1.7-3
- warn for prod release
- fix bug in tarball validation
* Tue Mar 10 2015 Jay Greguske <jgregusk@redhat.com> 1.7-2
- more robust validation of repositories file
- fix repositories file check
- report lineage when uploading new image
- copy all lineage into a repo during upload

* Tue Mar 10 2015 Jay Greguske <jgregusk@redhat.com> 1.7-1
- deploy dock-pulp-restore
- 1.7 release
- order image listings
- implement dock-pulp-restore.py
- handle subtask failure better
- fix json dumping again
- fix json dump bug
- require password
- fix bootstrap to create properly

* Wed Mar 04 2015 Jay Greguske <jgregusk@redhat.com> 1.6-1
- up to 1.6
- fix crane export bug
- implement tag --remove
- fix cloning bug with redirect urls

* Fri Feb 27 2015 Jay Greguske <jgregusk@redhat.com> 1.5-1
- bump to 1.5
- implement create --title
- drop create --entitlement
- drop create --public
- minor tweaks
- tailored reporting of 500 errors
- require content-urls during creation
- add lots of CLI flexibility
- add internal error
- implement dock-pulp-confirm.py
- add registry and cdnhost constants
- rename create-everything

* Tue Feb 24 2015 Jay Greguske <jgregusk@redhat.com> 1.4-2
- warn on inconsistent scratchpad data
- update QA url
- fix tagging bug

* Mon Feb 23 2015 Jay Greguske <jgregusk@redhat.com> 1.4-1
- up to 1.4 we go
- integrated use of redhat-everything
- fixed a bug with listing uploads

* Tue Feb 17 2015 Jay Greguske <jgregusk@redhat.com> 1.3-1
- update spec to 1.3
- add upload --list and --remove
- add remove --list-orphans --remove
- implemented do_dump()
- moved errors to their own file

* Fri Feb 13 2015 Jay Greguske <jgregusk@redhat.com> 1.2-1
- implement do_clone() (jgregusk@redhat.com)
- capture 403s better (jgregusk@redhat.com)

* Wed Feb 11 2015 Jay Greguske <jgregusk@redhat.com> 1.1-1
- bump to 1.1 (jgregusk@redhat.com)
- implement do_empty
- add list --details
- fix upload bug
- ignore .pyo files
- fix directive listings
* Tue Feb 10 2015 Jay Greguske <jgregusk@redhat.com> 1.0-3
- fix up logging
- add some image checks before uploading (jgregusk@redhat.com)
- fix usage program name (jgregusk@redhat.com)
* Mon Feb 9 2015 Jay Greguske <jgregusk@redhat.com> 1.0-2
- initial release
