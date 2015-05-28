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
