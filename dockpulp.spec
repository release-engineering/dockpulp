Name:		dockpulp
Version:	1.59
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
Requires: gnupg
Requires: python-six
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
install -pm 0755 bin/dock-pulp $RPM_BUILD_ROOT%{_bindir}/dock-pulp
install -pm 0755 bin/dock-pulp-bootstrap $RPM_BUILD_ROOT%{_bindir}/dock-pulp-bootstrap
install -pm 0755 bin/dock-pulp-restore $RPM_BUILD_ROOT%{_bindir}/dock-pulp-restore
install -pm 0755 bin/dock-pulp-recreate-hidden $RPM_BUILD_ROOT%{_bindir}/dock-pulp-recreate-hidden

%clean
rm -rf $RPM_BUILD_ROOT


%files
%defattr(-,root,root,-)
%{python_sitelib}/*
%{_bindir}/*
%doc LICENSE


%changelog
* Thu Oct 11 2018 Brendan Reilly <breilly@redhat.com> 1.59-1
- Bumping version for release (breilly@redhat.com)
- updated unit tests for 'protected' removal (breilly@redhat.com)
- removal of 'protected' option from CLI (breilly@redhat.com)

* Fri Oct 05 2018 Brendan Reilly <breilly@redhat.com> 1.58-1
- Bumping for new version (breilly@redhat.com)
- Bug fixes related to python 3 change (breilly@redhat.com)
- Fix arg parsing for --no-paginate (lucarval@redhat.com)
- Add python3 tests to travis (breilly@redhat.com)
- Updating unit tests for py3 (breilly@redhat.com)
- Made dockpulp python 3 compatible (breilly@redhat.com)
- Fix content list pagination with since filter (lucarval@redhat.com)
- Paginate repo contents to avoid pulp memory issues (lucarval@redhat.com)

* Fri Oct 05 2018 Brendan Reilly <breilly@redhat.com>
- Bug fixes related to python 3 change (breilly@redhat.com)
- Fix arg parsing for --no-paginate (lucarval@redhat.com)
- Add python3 tests to travis (breilly@redhat.com)
- Updating unit tests for py3 (breilly@redhat.com)
- Made dockpulp python 3 compatible (breilly@redhat.com)
- Fix content list pagination with since filter (lucarval@redhat.com)
- Paginate repo contents to avoid pulp memory issues (lucarval@redhat.com)

* Wed Aug 22 2018 Brendan Reilly <breilly@redhat.com> 1.56-1
- Bumping version for release (breilly@redhat.com)
- Avoid traceback when computing ancestry (twaugh@redhat.com)

* Thu Aug 16 2018 Brendan Reilly <breilly@redhat.com> 1.55-1
- Bumping version for release (breilly@redhat.com)
- Better output when listing orphan docker tags (twaugh@redhat.com)
- syncRepo: make a list of keys before sorting (twaugh@redhat.com)
- syncRepo: use more efficient query for new units (OSBS-6046)
  (twaugh@redhat.com)
- listRepos: new 'since' parameter (a datetime) (twaugh@redhat.com)
- watch: return the task report (twaugh@redhat.com)
- Include additional unit types for orphan management (twaugh@redhat.com)
- listRepos: calculate image inheritance (twaugh@redhat.com)

* Fri Jul 20 2018 Brendan Reilly <breilly@redhat.com> 1.54-1
- Bumping version for release (breilly@redhat.com)
- Fixed unit tests for manifest tag change (breilly@redhat.com)
- Fixed confirm to support manifest tag changes (breilly@redhat.com)
- syncRepo: copy new files with an explicit filter (mlangsdo@redhat.com)

* Thu Jun 14 2018 Brendan Reilly <breilly@redhat.com> 1.53-1
- Bumping version for release (breilly@redhat.com)

* Thu Jun 14 2018 Brendan Reilly <breilly@redhat.com> 1.52-1
- confirm sigstore will ignore invalid signatures instead of failing
  (breilly@redhat.com)
- Updated unit tests to support removal of PULP_MANIFEST check from sigstore
  confirm (breilly@redhat.com)
- Removed check based on PULP_MANIFEST to follow new requirements
  (breilly@redhat.com)
- No Pulp response fails instead of warns (breilly@redhat.com)
- Added unit test for is_task_successful (breilly@redhat.com)
- Skipped result will now be treated correctly (breilly@redhat.com)
- Changed redirect verification to expect repo id (breilly@redhat.com)
- Added unit tests (breilly@redhat.com)
- Added option to specify feed for sync (breilly@redhat.com)

* Wed Apr 11 2018 Brendan Reilly <breilly@redhat.com> 1.51-1
- bumped version for release (breilly@redhat.com)
- Updated unit tests to support manifest tag lists (breilly@redhat.com)
- Multiple tags can now be displayed for manifests (breilly@redhat.com)
- Updated unit tests to reflect HIDDEN deprecation (breilly@redhat.com)
- Deprecating HIDDEN repo by providing hidden origin repos for each repo
  (breilly@redhat.com)
- Add autopublish update to updateRepo (bfontecc@redhat.com)
- Output tasks json in silent mode (lucarval@redhat.com)

* Thu Mar 15 2018 Brendan Reilly <breilly@redhat.com> 1.50-1
- Bumping version for release (breilly@redhat.com)
- Added unit tests (breilly@redhat.com)
- Fixed bug with schema 2 history output (breilly@redhat.com)
- bugfix for schema printout (breilly@redhat.com)

* Tue Feb 27 2018 Brendan Reilly <breilly@redhat.com> 1.49-1
- bumping version for release (breilly@redhat.com)
- bugfix for updating redirect (breilly@redhat.com)
- Added unit tests for new repo note value include_in_download_service
  (breilly@redhat.com)
- Updated create/update/list for new repo note value (breilly@redhat.com)

* Thu Feb 08 2018 Brendan Reilly <breilly@redhat.com> 1.48-1
- Bumped version for release (breilly@redhat.com)
- Fixed unit tests, bug with updateRepo (breilly@redhat.com)
- Initialized rel_url as None in the case of no url being supplied
  (breilly@redhat.com)
- Added unit tests (breilly@redhat.com)
- Added rel-url for docker_rsync_distributor (breilly@redhat.com)
- Removed unnecessary dictionary (breilly@redhat.com)
- Made repo to output copy shallow (breilly@redhat.com)
- Restructured do_list for clarity (breilly@redhat.com)
- Added caplog to do_list test (breilly@redhat.com)
- Changed error dict to variable (breilly@redhat.com)
- Cleaned up do_list code and made variables more clear (breilly@redhat.com)
- Added unit tests for do_list and confirm (breilly@redhat.com)
- Fixed 'reachable' to actually reflect reachable content; added return to
  do_list for unit testing (breilly@redhat.com)
- Added helper function for error checking in confirm (breilly@redhat.com)
- Cleaning up unneeded dictionary key (breilly@redhat.com)
- Silent confirm now reports number of failing repos (breilly@redhat.com)
- Added confirmation of mediatype (breilly@redhat.com)
- Fixed grouping issue with manifest list (breilly@redhat.com)
- Made manifest list output an option (breilly@redhat.com)
- Added support for listing and confirming manifest lists (breilly@redhat.com)
- Automatic commit of package [dockpulp] release [1.47-1]. (breilly@redhat.com)
- bumping version for release (breilly@redhat.com)

* Fri Dec 01 2017 Brendan Reilly <breilly@redhat.com> 1.47-1
- bumping version for release (breilly@redhat.com)
- install specific versions of test package to avoid test package update breaks
  (breilly@redhat.com)
- Fixed sigstore distributors to match requirements (breilly@redhat.com)

* Mon Nov 27 2017 Brendan Reilly <breilly@redhat.com> 1.46-1
- Bumping version for release (breilly@redhat.com)
- Added conf info and unit testing for switchover (breilly@redhat.com)
- Added switchover func for release order (breilly@redhat.com)
- schema option now outputs image data as expected (breilly@redhat.com)
- Added schema option to display schema version of each manifest
  (breilly@redhat.com)
- Added unit test for associate type_id (breilly@redhat.com)
- Added switchover capability for sigstore distributors (breilly@redhat.com)
- Added unittests for name restrictions (breilly@redhat.com)
- Restrict repo id based on crane requirements (breilly@redhat.com)
- Confirm directive now outputs proper json in silent mode
  (amisstea@redhat.com)
- Log the actual status code when >= 500 (twaugh@redhat.com)

* Fri Oct 13 2017 Brendan Reilly <breilly@redhat.com> 1.45-1
- bumping version for release (breilly@redhat.com)
- Limited image id search (breilly@redhat.com)
- Added optional config for pulp distributor switchovers (breilly@redhat.com)
- Changed release options to support rsync distributor (breilly@redhat.com)

* Thu Sep 28 2017 Brendan Reilly <breilly@redhat.com> 1.44-1
- Bumping version for release (breilly@redhat.com)
- Fixed breaking change for atomic reactor (breilly@redhat.com)
- Delete now has publish option to remove content from crane and empty more
  efficient (breilly@redhat.com)
- Improved sync with filter copy (breilly@redhat.com)
- Small update to schema2 listing (breilly@redhat.com)
- dockpulp can now handle schema2 manifests (breilly@redhat.com)
- Fixed bug with prefix in sigstore repo confirm (breilly@redhat.com)
- Improved sigstore repo checking (breilly@redhat.com)
- Changed request retry implementation (breilly@redhat.com)

* Thu Jul 27 2017 Brendan Reilly <breilly@redhat.com> 1.43-1
- bumping version for release (breilly@redhat.com)
- Fixed bug with cloning repos with distribution defined and rurl enforcement
  (breilly@redhat.com)
- Fixed bug with distribution update (breilly@redhat.com)
- Don't show tag if manifest has tag set to None (vrutkovs@redhat.com)
- New pulp (2.13) doesn't store tags along with manifest, so it should be
  looked up additionally (vrutkovs@redhat.com)
- Added crane vs pulp checking to sigstore confirm (breilly@redhat.com)
- Removed host from rel-url to match new requirements (breilly@redhat.com)
- Fixed bug with distribution and hidden repos (breilly@redhat.com)
- Sigstore repo can now be listed and confirmed (breilly@redhat.com)
- Set relative_url for redhat-sigstore (breilly@redhat.com)
- Automatic commit of package [dockpulp] release [1.42-1]. (breilly@redhat.com)
- Bumping version for release (breilly@redhat.com)

* Thu Jun 22 2017 Brendan Reilly <breilly@redhat.com> 1.42-1
- Bumping version for release (breilly@redhat.com)
- Enforce distribution for certain envs (breilly@redhat.com)
- Refactored distribution conf into json (breilly@redhat.com)
- Name enforce now checks product-line (breilly@redhat.com)
- Added configurable naming enforcement for repo-ids and content-urls
  (breilly@redhat.com)
- Added distribution mapping to signatures (breilly@redhat.com)
- Added missing error return (breilly@redhat.com)

* Thu Apr 06 2017 Brendan Reilly <breilly@redhat.com> 1.41-1
- Bumping version for release (breilly@redhat.com)
- Added one more distributor for sigstore (breilly@redhat.com)
- Made dock-pulp-bootstrap idempotent, added sigstore repo setup
  (breilly@redhat.com)
- Make source and installation filenames consistent (rmcgover@redhat.com)
- Added noprefix option for create and clone (breilly@redhat.com)
- Clone now copies V2 images (breilly@redhat.com)
- Added option for distribution field in repos (breilly@redhat.com)
- Added unit tests for associate / disassociate (breilly@redhat.com)
- Fixed library docker-id bug, added unit tests for createRepo
  (breilly@redhat.com)
- Added option to set signatures to sign repos (breilly@redhat.com)
- Added unit test for clone (breilly@redhat.com)
- Unit test for do_associate (breilly@redhat.com)
- Unit test for do_ancestry (breilly@redhat.com)
- Make tests a module to aid local coverage testing (twaugh@redhat.com)
- Added unit test for do_create (breilly@redhat.com)
- Fixed repo file check (breilly@redhat.com)
- Added unit test for pulp login (breilly@redhat.com)
- Moved CLI code to separate file to allow for testing (breilly@redhat.com)
- Updating titoprops for new version (breilly@redhat.com)

* Tue Dec 20 2016 Brendan Reilly <breilly@redhat.com> 1.40-1
- Bumping version for release (breilly@redhat.com)
- Added silent option for json dump of repo listing (breilly@redhat.com)
- Refactored confirm code for future unit testing (breilly@redhat.com)

* Fri Nov 18 2016 Brendan Reilly <breilly@redhat.com> 1.39-1
- Bumping version for release (breilly@redhat.com)
- Fixed createrepo enforcement (breilly@redhat.com)

* Tue Nov 15 2016 Brendan Reilly <breilly@redhat.com> 1.38-1
- bumping version for release (breilly@redhat.com)
- Fixed flake8 errors (breilly@redhat.com)
- Fix for 'v1_labels' keyerror (breilly@redhat.com)

* Mon Nov 14 2016 Brendan Reilly <breilly@redhat.com> 1.37-1
- Bumping version for 1.37 release (breilly@redhat.com)
- Added check-layers functionality (breilly@redhat.com)
- Added unit testing for retries (breilly@redhat.com)
- Added support for v1 label listing (breilly@redhat.com)
- Added listing label support for v2 manifests (breilly@redhat.com)
- Dockpulp checks update redirect-url to fit pulp standards
  (breilly@redhat.com)
- Added decorator to cut down on duplicate code (breilly@redhat.com)
- Added configurable retries to make requests more resilient to infra hiccups
  (breilly@redhat.com)
- Adding version of pydocstyle into tox.ini (lkolacek@redhat.com)
- Fixing flake8 error E501 - line too long (lkolacek@redhat.com)
- Removing result from arguments (lkolacek@redhat.com)
- Adding parametrization of arguments for a test functions
  (lkolacek@redhat.com)
- Adding new tests for Pulp instance (lkolacek@redhat.com)
- Fix E501 line too long (n > 100 characters) (vrutkovs@redhat.com)
- Removing corrected errors and adding new ones (lkolacek@redhat.com)
- content-url is now enforced to end with '/docker-id' (breilly@redhat.com)
- Remove import of version from setup.py (csomh@redhat.com)
- Setting environment for dockpulp unit testing (lkolacek@redhat.com)

* Fri Sep 23 2016 Brendan Reilly <breilly@redhat.com> 1.36-1
- Bumping version for release (breilly@redhat.com)
- Automatic commit of package [dockpulp] release [1.35-1]. (breilly@redhat.com)
- Bumping version for release (breilly@redhat.com)
- Fix some doc flake8 errors (lucarval@redhat.com)
- Fix flake8 F841 reports (twaugh@redhat.com)
- Fix 'W601 .has_key() is deprecated, use 'in'' (vrutkovs@redhat.com)

* Fri Sep 23 2016 Brendan Reilly <breilly@redhat.com> 1.35-1
- Bumping version for release (breilly@redhat.com)
- Fixed merging issue with whitespace changes (breilly@redhat.com)
- Added force-refresh option on release (breilly@redhat.com)
- whitespace changes only (twaugh@redhat.com)

* Fri Sep 02 2016 Brendan Reilly <breilly@redhat.com> 1.34-1
- Bumped version for release (breilly@redhat.com)
- Updated tito.props (breilly@redhat.com)
- Report missing v2 blobs (twaugh@redhat.com)
- Do not assume there is a docker_tag unit for each manifest's tag name
  (twaugh@redhat.com)

* Wed Aug 31 2016 Brendan Reilly <breilly@redhat.com> 1.33-1
- Bumping version for release (breilly@redhat.com)
- Fix confirm errors caused by '(active)' changes (twaugh@redhat.com)

* Tue Aug 30 2016 Brendan Reilly <breilly@redhat.com> 1.32-1
- Bumping version for release (breilly@redhat.com)
- Cleaned up history output (breilly@redhat.com)
- Added --manifests option for cleaner list output (breilly@redhat.com)
- Tags that can be pulled are now marked as 'active' (breilly@redhat.com)
- Merge pull request #82 from lcarva/clean-orphans (breilly@redhat.com)
- Display and remove v1 and v2 orphaned content (lucarval@redhat.com)

* Tue Aug 23 2016 Brendan Reilly <breilly@redhat.com> 1.31-1
- Only add skip fast forward if true (breilly@redhat.com)
- Added release order for distributors (breilly@redhat.com)

* Thu Aug 18 2016 Brendan Reilly <breilly@redhat.com> 1.30-1
- Bumping version for release (breilly@redhat.com)

* Thu Aug 18 2016 Brendan Reilly <breilly@redhat.com> 1.3-1
- Bumping version for release (breilly@redhat.com)
- get_versions: skip layers if they don't have docker_version set
  (vrutkovs@redhat.com)
- confirm: avoid traceback for unpublished v2 content (twaugh@redhat.com)

* Thu Aug 11 2016 Brendan Reilly <breilly@redhat.com> 1.29-1
- Added dock-pulp-recreate-hidden to dockpulp.spec (breilly@redhat.com)
- Bumping version for release (breilly@redhat.com)
- confirm: choose whether to check v2 content based on /v2/ response
  (twaugh@redhat.com)
- CLI: 'remove' should not calculate unneeded layers for hidden repo
  (twaugh@redhat.com)

* Wed Jul 27 2016 Brendan Reilly <breilly@redhat.com> 1.28-1
- bumped version for release (breilly@redhat.com)
- confirm: verify 'name' key in manifest (twaugh@redhat.com)
- confirm: test 'name' from tags/list (twaugh@redhat.com)
- Merge pull request #73 from twaugh/sync-enable-v1 (breilly@redhat.com)
- copy_filters: new method, used by recreate-hidden script (jluza@redhat.com)
- sync: fix enable_v1 setting (twaugh@redhat.com)
- listRepos: avoid traceback on stale scratch pad data (twaugh@redhat.com)

* Tue Jul 12 2016 Brendan Reilly <breilly@redhat.com> 1.27-1
- Bumping version for new build (breilly@redhat.com)
- history will now skip over hidden repo, missing manifests
  (breilly@redhat.com)
- Added skip fast forward option (breilly@redhat.com)
- Allowed upstream name arg for syncs (breilly@redhat.com)
- Merge pull request #67 from twaugh/sync-to-hidden (breilly@redhat.com)
- Confirm does not test if there is no v1 or v2 content. Fixed issue with
  silent output not reporting v1 error if v2 content is fine.
  (breilly@redhat.com)
- syncRepo: no need to copy to hidden repo if it was sync destination
  (twaugh@redhat.com)

* Fri Jul 01 2016 Brendan Reilly <breilly@redhat.com> 1.26-1
- Bumped version for new build (breilly@redhat.com)
- Updated ancestry call to avoid index error (breilly@redhat.com)
- Fixed logging for python <2.7 (breilly@redhat.com)
- Clarified dry run output (breilly@redhat.com)
- Added v2 support to hidden repo recreate script (breilly@redhat.com)
- Wrote script to restore hidden repo if parity is lost (breilly@redhat.com)

* Thu Jun 30 2016 Brendan Reilly <breilly@redhat.com> 1.25-1
- Bumped version for new build (breilly@redhat.com)
- Merge pull request #63 from twaugh/version-attribute (breilly@redhat.com)
- Cleaned up do_list code (breilly@redhat.com)
- Added history option to list (breilly@redhat.com)
- Set __version__ attribute in dockpulp module (twaugh@redhat.com)
- Updated list output to be more technically correct (breilly@redhat.com)
- Bugfix for extraneous list manifest print (breilly@redhat.com)
- Added prefix getter to pulp object (breilly@redhat.com)
- Cleaned up code (breilly@redhat.com)
- Added password and username option to sync, fixed typo (breilly@redhat.com)
- Confirm now uses the right default pulp redirect for repos without a redirect
  set (breilly@redhat.com)

* Tue Jun 28 2016 Brendan Reilly <breilly@redhat.com> 1.24-1
- Cleaned up confirm, added check for tags in pulp/crane (breilly@redhat.com)
- Updated confirm for v2 manifests and blobs (breilly@redhat.com)

* Fri Jun 24 2016 Brendan Reilly <breilly@redhat.com> 1.23-1
- Updated sync to always copy new images and manifests to HIDDEN repo
  (breilly@redhat.com)
- Updated remove to work with v2 manifests (breilly@redhat.com)
- Removed upstream_name parameter (breilly@redhat.com)
- Updated copy to work with v2 manifests and blobs (breilly@redhat.com)
- Updated sync to allow auth (breilly@redhat.com)
- Added v2 support for dockpulp list (breilly@redhat.com)
- Fixed some typos regarding regex/glob (breilly@redhat.com)

* Fri May 27 2016 Brendan Reilly <breilly@redhat.com> 1.22-1
- Removed extraneous bool checks for silent output (breilly@redhat.com)
- Removed need for curl in confirm function, now accepts cert and key and uses
  python requests. Added in machine readable output for confirm as a --silent
  option. (breilly@redhat.com)

* Fri May 20 2016 Brendan Reilly <breilly@redhat.com> 1.21-1
- Confirm can now be provided certs, ca certs, and keys to check protected
  repositories. (breilly@redhat.com)
- Fixed typo (breilly@redhat.com)

* Mon May 02 2016 Brendan Reilly <breilly@redhat.com> 1.20-1
- Added in support for distributor interactions (breilly@redhat.com)
- Added in support for distributor interactions (breilly@redhat.com)

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
