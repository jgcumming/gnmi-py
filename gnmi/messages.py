# -*- coding: utf-8 -*-
# Copyright (c) 2020 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.
"""
gnmi.messages
~~~~~~~~~~~~~~~~

gNMI messags wrappers

"""

import re
import collections

from typing import List
import google.protobuf as _
import grpc

from gnmi.proto import gnmi_pb2 as pb  # type: ignore
from gnmi import util

class CapabilitiesResponse_(object):
    r"""Represents a gnmi.CapabilitiesResponse message

    """

    def __init__(self, response):
        self.raw = response

    @property
    def supported_models(self):
        for model in self.raw.supported_models:
            yield {
                "name": model.name,
                "organization": model.organization,
                "version": model.version
            }
    models = supported_models

    @property
    def supported_encodings(self):
        return self.raw.supported_encodings
    encodings = supported_encodings

    @property
    def gnmi_version(self):
        return self.raw.gNMI_version
    version = gnmi_version

class Update_(object):
    r"""Represents a gnmi.Update message

    """

    def __init__(self, update):
        self.raw = update

    @property
    def path(self):
        return Path_(self.raw.path)

    @property
    def value(self):
        return util.extract_value(self.raw)
    val = value

    @property
    def duplicates(self):
        return self.raw.duplicates

class Notification_(object):
    r"""Represents a gnmi.Notification message

    """

    def __init__(self, notification):
        self.raw = notification
    
    def __iter__(self):
        return self.updates

    @property
    def prefix(self):
        return Path_(self.raw.prefix)
    
    @property
    def timestamp(self):
        return self.raw.timestamp

    @property
    def updates(self):
        
        for update in self.raw.update:
            yield Update_(update)

class GetResponse_(object):
    r"""Represents a gnmi.GetResponse message

    """

    def __init__(self, response):
        self.raw = response

    def __iter__(self):
        return self.notifications
        
    @property
    def notifications(self):
        for notification in self.raw.notification:
            yield Notification_(notification)


class SubscribeResponse_(object):
    r"""Represents a gnmi.SubscribeResponse message

    """

    def __init__(self, response):
        self.raw = response

    # @property
    # def sync_response(self):
    #     pass
    
    @property
    def update(self):
        return Notification_(self.raw.update)

class PathElem_(object):
    r"""Represents a gnmi.PathElem message

    """

    def __init__(self, elem):
        self.raw = elem
        self.key = {}
        if hasattr(elem, "key"):
            self.key = self.raw.key
        self.name = self.raw.name

class Path_(object):
    r"""Represents a gnmi.Pasth message

    """

    RE_ORIGIN = re.compile(r"(?:(?P<origin>[\w\-]+)?:)?(?P<path>\S+)$")
    RE_COMPONENT = re.compile(r'''
^
(?P<pname>[^[]+)
(\[(?P<key>[a-zA-Z0-9\-\/\.]+)
=
(?P<value>.*)
\])?$
''', re.VERBOSE)
    
    def __init__(self, path):
        self.raw = path

    def __str__(self):
        return self.to_string()
    
    def __add__(self, other: 'Path_') -> 'Path_':
        elems = []

        for elem in self.elements:
            elems.append(elem.raw)

        for elem in other.elements:
            elems.append(elem.raw)

        return Path_(pb.Path(elem=elems)) # type: ignore


    @property
    def elements(self):
        elem = self.raw.elem
        
        # use v3 if present
        if len(self.raw.element) > 0:
            elem = self.raw.element
        
        for elem in self.raw.elem:
            yield PathElem_(elem)

    @property
    def origin(self):
        return self.raw.origin
    
    @property
    def target(self):
        return self.raw.target

    def to_string(self):

        path = ""
        for elem in self.elements:
            path += "/" + util.escape_string(elem.name, "/")
            for key, val in elem.key.items():
                val = util.escape_string(val, "]")
                path += "[" + key + "=" + val + "]"

        if self.origin:
            path = ":".join([self.origin, path])
        
        return path
    
    @classmethod
    def from_string(cls, path):

        if not path:
            return cls(pb.Path(origin=None, elem=[])) # type: ignore
        
        names: List[str] = []
        elems: list = []
        
        path = path.strip()
        origin = None

        match = cls.RE_ORIGIN.search(path)
        origin = match.group("origin")
        path = match.group("path")
        
        if path:
            names = [re.sub(r"\\", "", name) for name in re.split(r"(?<!\\)/", path) if name]
        
        for name in names:
            match = cls.RE_COMPONENT.search(name)
            if not match:
                raise ValueError("path component parse error: %s" % name)

            if match.group("key") is not None:
                _key = {}
                for keyval in re.findall(r"\[([^]]*)\]", name):
                    val = keyval.split("=")[-1]
                    _key[keyval.split("=")[0]] = val

                pname = match.group("pname")
                elem = pb.PathElem(name=pname, key=_key) # type: ignore
                elems.append(elem)
            else:
                elems.append(pb.PathElem(name=name, key={})) # type: ignore
        
        return cls(pb.Path(origin=origin, elem=elems)) # type: ignore

class Status_(collections.namedtuple('Status_', 
        ('code', 'details', 'trailing_metadata')), grpc.Status):
    
    @classmethod
    def from_call(cls, call):
        return cls(call.code(), call.details(), call.trailing_metadata())
