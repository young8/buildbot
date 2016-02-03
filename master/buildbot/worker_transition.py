# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

"""
Utility functions to support transition from "slave"-named API to
"worker"-named.

Use of old API generates Python warning which may be logged, ignored or treated
as an error using Python builtin warnings API.
"""

import functools
import sys
import warnings

from twisted.python.deprecate import deprecatedModuleAttribute as _deprecatedModuleAttribute
from twisted.python.deprecate import getWarningMethod
from twisted.python.deprecate import setWarningMethod
from twisted.python.versions import Version


__all__ = (
    "DeprecatedWorkerNameWarning",
    "define_old_worker_class", "define_old_worker_property",
    "define_old_worker_method", "define_old_worker_func",
    "WorkerAPICompatMixin",
    "deprecated_worker_class",
    "setupWorkerTransition",
    "deprecatedWorkerModuleAttribute",
)

# TODO:
# * Properly name classes and methods.
# * Aliases are defined even they usage will be forbidden later.
# * function wrapper is almost identical to method wrapper (they are both
#   just functions from Python side of view), probably method wrapper should
#   be dropped.
# * At some point old API support will be dropped and this module will be
#   removed. It's good to think now how this can be gracefully done later.
#   For example, if I explicitly configure warnings in buildbot.tac template
#   now, later generated from such template buildbot.tac files will break.


_WORKER_WARNING_MARK = "[WORKER]"


def _compat_name(new_name, compat_name=None):
    """Returns old API ("slave") name for new name ("worker").

    >>> assert _compat_name("Worker") == "Slave"
    >>> assert _compat_name("SomeWorkerStuff") == "SomeSlaveStuff"
    >>> assert _compat_name("SomeWorker", compat_name="SomeBuildSlave") == \
        "SomeBuildSlave"

    If `name` is not specified old name is construct by replacing:
        "worker" -> "slave",
        "Worker" -> "Slave".

    For the sake of simplicity of usage if `name` argument is specified
    it will returned as the result.
    """

    if compat_name is not None:
        assert "slave" in compat_name.lower()
        assert "worker" in new_name.lower()
        return compat_name

    compat_replacements = {
        "worker": "slave",
        "Worker": "Slave",
    }

    compat_name = new_name
    assert "slave" not in compat_name.lower()
    assert "worker" in compat_name.lower()
    for new_word, old_word in compat_replacements.iteritems():
        compat_name = compat_name.replace(new_word, old_word)

    assert compat_name != new_name
    assert "slave" in compat_name.lower()
    assert "worker" not in compat_name.lower()

    return compat_name


# DeprecationWarning or PendingDeprecationWarning may be used as
# the base class, but by default deprecation warnings are disabled in Python,
# so by default old-API usage warnings will be ignored - this is not what
# we want.
class DeprecatedWorkerAPIWarning(Warning):
    """Base class for deprecated API warnings."""


class DeprecatedWorkerNameWarning(DeprecatedWorkerAPIWarning):
    """Warning class for use of deprecated classes, functions, methods
    and attributes.
    """


# Separate warnings about deprecated modules from other deprecated
# identifiers.  Deprecated modules are loaded only once and it's hard to
# predict in tests exact places where warning should be issued (in contrast
# warnings about other identifiers will be issued every usage).
class DeprecatedWorkerModuleWarning(DeprecatedWorkerAPIWarning):
    """Warning class for use of deprecated modules."""


# TODO: make stacklevel relative to caller function
def on_deprecated_name_usage(message, stacklevel=None, filename=None,
                             lineno=None):
    """Hook that is ran when old API name is used."""

    if filename is None:
        if stacklevel is None:
            # Warning will refer to the caller of the caller of this function.
            stacklevel = 3

        warnings.warn(DeprecatedWorkerNameWarning(message), None, stacklevel)

    else:
        assert stacklevel is None

        if lineno is None:
            lineno = 0

        warnings.warn_explicit(
            DeprecatedWorkerNameWarning(message),
            DeprecatedWorkerNameWarning,
            filename, lineno)


def on_deprecated_module_usage(message, stacklevel=None):
    """Hook that is ran when old API module is used."""

    if stacklevel is None:
        # Warning will refer to the caller of the caller of this function.
        stacklevel = 3

    warnings.warn(DeprecatedWorkerModuleWarning(message), None, stacklevel)


def setupWorkerTransition():
    """Hook Twisted deprecation machinery to use custom warning class
    for Worker API deprecation warnings."""

    default_warn_method = getWarningMethod()

    def custom_warn_method(message, category, stacklevel):
        if _WORKER_WARNING_MARK in message:
            # Message contains our mark - it's Worker API Renaming warning,
            # issue it appropriately.
            message = message.replace(_WORKER_WARNING_MARK, "")
            if stacklevel is not None:
                stacklevel += 1
            warnings.warn(
                DeprecatedWorkerNameWarning(message), message, stacklevel)
        else:
            # Other's warning message
            default_warn_method(message, category, stacklevel)

    setWarningMethod(custom_warn_method)


def deprecatedWorkerModuleAttribute(scope, attribute, compat_name=None):
    """This is similar to Twisted's deprecatedModuleAttribute, but for
    Worker API Rename warnings.
    """

    module_name = scope["__name__"]
    assert module_name in sys.modules, "scope must be module, i.e. locals()"
    assert sys.modules[module_name].__dict__ is scope, \
        "scope must be module, i.e. locals()"

    attribute_name = scope.keys()[scope.values().index(attribute)]

    compat_name = _compat_name(attribute_name, compat_name=compat_name)

    scope[compat_name] = attribute

    _deprecatedModuleAttribute(
        Version("Buildbot", 0, 9, 0),
        _WORKER_WARNING_MARK + "Use {0} instead.".format(attribute_name),
        module_name, compat_name)


def deprecated_worker_class(cls, class_name=None):
    assert issubclass(cls, object)

    compat_name = _compat_name(cls.__name__, compat_name=class_name)

    def __new__(instance_cls, *args, **kwargs):
        on_deprecated_name_usage(
            "'{old}' class is deprecated, use '{new}' instead.".format(
                new=cls.__name__, old=compat_name))
        if cls.__new__ is object.__new__:
            # object.__new__() doesn't accept arguments.
            instance = cls.__new__(instance_cls)
        else:
            # Class has overloaded __new__(), pass arguments to it.
            instance = cls.__new__(instance_cls, *args, **kwargs)

        return instance

    compat_class = type(compat_name, (cls,), {
        "__new__": __new__,
        "__module__": cls.__module__,
        "__doc__": cls.__doc__,
        })

    return compat_class


def define_old_worker_class(scope, cls, compat_name=None):
    """Define old-named class that inherits new names class.

    Useful for instantiable classes.
    """

    compat_class = deprecated_worker_class(cls, class_name=compat_name)
    scope[compat_class.__name__] = compat_class


def define_old_worker_property(scope, new_name, compat_name=None):
    """Define old-named property inside class."""
    compat_name = _compat_name(new_name, compat_name=compat_name)
    assert compat_name not in scope

    def get(self):
        on_deprecated_name_usage(
            "'{old}' attribute is deprecated, use '{new}' instead.".format(
                new=new_name, old=compat_name))
        return getattr(self, new_name)

    scope[compat_name] = property(get)


def define_old_worker_method(scope, method, compat_name=None):
    """Define old-named method inside class."""
    method_name = method.__name__

    compat_name = _compat_name(method_name, compat_name=compat_name)

    assert compat_name not in scope

    def old_method(self, *args, **kwargs):
        on_deprecated_name_usage(
            "'{old}' method is deprecated, use '{new}' instead.".format(
                new=method_name, old=compat_name))
        return getattr(self, method_name)(*args, **kwargs)

    functools.update_wrapper(old_method, method)

    scope[compat_name] = old_method


def define_old_worker_func(scope, func, compat_name=None):
    """Define old-named function."""
    compat_name = _compat_name(func.__name__, compat_name=compat_name)

    def old_func(*args, **kwargs):
        on_deprecated_name_usage(
            "'{old}' function is deprecated, use '{new}' instead.".format(
                new=func.__name__, old=compat_name))
        return func(*args, **kwargs)

    functools.update_wrapper(old_func, func)

    scope[compat_name] = old_func


class WorkerAPICompatMixin(object):
    """Mixin class for classes that have old-named worker attributes."""

    def __getattr__(self, name):
        if name not in self.__compat_attrs:
            raise AttributeError(
                "'{class_name}' object has no attribute '{attr_name}'".format(
                    class_name=self.__class__.__name__,
                    attr_name=name))

        new_name = self.__compat_attrs[name]

        # TODO: Log class name, operation type etc.
        on_deprecated_name_usage(
            "'{old}' attribute is deprecated, use '{new}' instead.".format(
                new=new_name, old=name))

        return getattr(self, new_name)

    def __setattr__(self, name, value):
        if name in self.__compat_attrs:
            new_name = self.__compat_attrs[name]
            # TODO: Log class name, operation type etc.
            on_deprecated_name_usage(
                "'{old}' attribute is deprecated, use '{new}' instead.".format(
                    new=new_name, old=name))
            return setattr(self, new_name, value)
        else:
            object.__setattr__(self, name, value)

    @property
    def __compat_attrs(self):
        # It's unreliable to initialize attributes in __init__() since
        # old-style classes are used and parent initializers are mostly
        # not called.
        if "_compat_attrs_mapping" not in self.__dict__:
            self.__dict__["_compat_attrs_mapping"] = {}
        return self._compat_attrs_mapping

    def _registerOldWorkerAttr(self, attr_name, name=None):
        """Define old-named attribute inside class instance."""
        compat_name = _compat_name(attr_name, compat_name=name)
        assert compat_name not in self.__dict__
        assert compat_name not in self.__compat_attrs
        self.__compat_attrs[compat_name] = attr_name
