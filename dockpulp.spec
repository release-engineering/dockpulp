Name:		dockpulp
Version:	1.11
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
install -d $RPM_BUILD_ROOT%{_sysconfdir}
install -pm 0644 dockpulp/* $RPM_BUILD_ROOT%{python_sitelib}/dockpulp
install -pm 0755 bin/dock-pulp.py $RPM_BUILD_ROOT%{_bindir}/dock-pulp
install -pm 0755 bin/dock-pulp-bootstrap.py $RPM_BUILD_ROOT%{_bindir}/dock-pulp-bootstrap
install -pm 0755 bin/dock-pulp-restore.py $RPM_BUILD_ROOT%{_bindir}/dock-pulp-restore
install -pm 0644 conf/dockpulp.conf $RPM_BUILD_ROOT%{_sysconfdir}


%clean
rm -rf $RPM_BUILD_ROOT


%files
%defattr(-,root,root,-)
%{python_sitelib}/*
%{_bindir}/*
%config(noreplace) %{_sysconfdir}/dockpulp.conf
%doc LICENSE


%changelog
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
