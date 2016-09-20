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


class DockPulpError(Exception):
    pass


class DockPulpConfigError(DockPulpError):
    pass


class DockPulpInternalError(DockPulpError):
    pass


class DockPulpLoginError(DockPulpError):
    pass


class DockPulpServerError(DockPulpError):
    pass


class DockPulpTaskError(DockPulpError):
    pass
