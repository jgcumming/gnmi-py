# -*- coding: utf-8 -*-
# Copyright (c) 2020 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.
"""
gnmi.session
~~~~~~~~~~~~~~~~

Implementation if gnmi.session API

"""
import grpc
import google.protobuf as _
from gnmi.proto import gnmi_pb2 as pb  # type: ignore
from gnmi.proto import gnmi_pb2_grpc  # type: ignore

from typing import Optional, Iterator

from gnmi import util
from gnmi.messages import CapabilitiesResponse_, GetResponse_, Path_, Status_
from gnmi.messages import SubscribeResponse_
from gnmi.structures import Metadata, Target, CertificateStore, Options
from gnmi.structures import GetOptions, SubscribeOptions
from gnmi.constants import DEFAULT_GRPC_PORT, MODE_MAP, DATA_TYPE_MAP
from gnmi.exceptions import GrpcError, GrpcDeadlineExceeded


class Session(object):
    r"""Represents a gNMI session

    Basic Usage:: 

        In [1]: from gnmi.session import Session
        In [2]: sess = Session(("veos3", 6030), 
        ...:     metadata=[("username", "admin"), ("password", "")])

    """

    def __init__(self,
                 target: Target,
                 metadata: Metadata = [],
                 certificates: CertificateStore = None,
                 host_override: str = ""):

        self._target = target
        self.metadata = metadata
        self._certificates = certificates
        self._host_override = host_override

        self._credentials = self._create_credentials()
        self._channel = self._create_channel()

        self._stub = gnmi_pb2_grpc.gNMIStub(self._channel)  # type: ignore

    @property
    def target(self) -> Target:
        _t: Target = (self._target[0], self._target[1] or DEFAULT_GRPC_PORT)
        return _t

    @property
    def addr(self):
        return "%s:%d" % self.target

    def _create_credentials(self):
        return []

    def _create_channel(self):
        # TODO: Implement secure channels
        return self._insecure_channel()

    def _insecure_channel(self):
        return grpc.insecure_channel(self.addr)  # type: ignore

    def _parse_path(self, path):
        if not path:
            path = Path_.from_string(path).raw
        elif isinstance(path, Path_):
            path = path.raw
        elif isinstance(path, str):
            path = Path_.from_string(path).raw
        elif isinstance(path, (list, tuple)):
            path = Path_.from_string("/".join(path)).raw
        else:
            raise ValueError("Failed to parse path: %s" % str(path))
        return path
    
    def capabilities(self) -> CapabilitiesResponse_:
        r"""Discover capabilities of the target

        Usage::
    
            In [3]: resp = sess.capabilities()

            In [4]: resp.gnmi_version                                                                      
            Out[4]: '0.7.0'

            In [5]: resp.supported_encodings                                                               
            Out[5]: [0, 4, 3]

            In [7]: for model in resp.supported_models: 
                ...:     print(model["name"], model["version"])  
                ...:     # print(model["organization])                                                                                  
            openconfig-system-logging 0.3.1
            openconfig-messages 0.0.1
            openconfig-platform-types 1.0.0
            arista-system-augments 
            openconfig-if-types 0.2.1
            openconfig-acl 1.0.2
            arista-intf-augments 
            openconfig-pf-srte 0.1.1
            openconfig-bgp 6.0.0
            ...
        
        :rtype: gnmi.messages.CapabilitiesResponse_
        """

        # if options.get("extension"):
        #     raise ValueError("'extension' is not implemented yet.")

        _cr = pb.CapabilityRequest()  # type: ignore

        try:
            response = self._stub.Capabilities(_cr, metadata=self.metadata)
        except grpc.RpcError as rpcerr:
            status = Status_.from_call(rpcerr)
            raise GrpcError(status)

        return CapabilitiesResponse_(response)

    def get(self, paths: list, options: GetOptions = {}) -> GetResponse_:
        r"""Get snapshot of state from the target

        Usage::

            In [8]: paths = [ 
            ...:     "/system/config/hostname", 
            ...:     "/system/memory/state/physical", 
            ...:     "/system/memory/state/reserved" 
            ...: ]
            In [9]: options={"prefix": "/", "encoding": "json"}                                            

            In [10]: resp = sess.get(paths, options)                                                        
            
            In [11]: for notif in resp: 
                ...:     for update in notif: 
                ...:         print(update.path, update.val) 
                ...:                                                                                                      
            /system/config/hostname veos3-782f
            /system/memory/state/physical 2062848000
            /system/memory/state/reserved 2007666688

        :param paths: List of paths
        :type paths: list
        :param options:
        :type options: gnmi.structures.GetOptions

        :rtype: gnmi.messages.GetResponse_
        """

        response: Optional[GetResponse_] = None
        prefix = self._parse_path(options.get("prefix"))
        encoding = util.get_gnmi_constant(options.get("encoding") or "json")
        type_ = DATA_TYPE_MAP.index(options.get("type") or "all")
        
        paths = [self._parse_path(path) for path in paths]
        
        _gr = pb.GetRequest(path=paths, prefix=prefix, encoding=encoding,
                            type=type_)  # type: ignore

        try:
            response = self._stub.Get(_gr, metadata=self.metadata)
        except grpc.RpcError as rpcerr:
            status = Status_.from_call(rpcerr)
            raise GrpcError(status)

        return GetResponse_(response)

    def set(self): ...

    def subscribe(self, paths: list, options: SubscribeOptions = {}) -> Iterator[SubscribeResponse_]:
        r"""Subscribe to state updates from the target

        Usage::

            In [57]: from gnmi.exceptions import GrpcDeadlineExceeded  
            In [58]: paths = [ 
            ...:     "/interface[name=Management1]", 
            ...:     "/interface[name=Ethernet1]" 
            ...: ]                                                                                                    

            In [59]: options = {
            ...:     "prefix": "/interfaces", 
            ...:     "mode": "stream",
            ...:     "submode": "on-change",
            ...:     "timeout": 5
            ...:  }          

            In [60]: responses = sess.subscribe(paths, options)                                                           

            In [61]: try: 
                ...:     for resp in responses: 
                ...:         prefix = resp.update.prefix 
                ...:         for update in resp.update.updates: 
                ...:             path = prefix + update.path 
                ...:             print(str(path), update.value) 
                ...: except GrpcDeadlineExceeded: 
                ...:     pass 
                ...:
            /interfaces/interface[name=Management1]/config/description 
            /interfaces/interface[name=Management1]/config/enabled True
            /interfaces/interface[name=Management1]/config/load-interval 300
            /interfaces/interface[name=Management1]/config/loopback-mode False
            <output-omitted>
            /interfaces/interface[name=Ethernet1]/config/description 
            /interfaces/interface[name=Ethernet1]/config/enabled True
            /interfaces/interface[name=Ethernet1]/config/load-interval 300
            /interfaces/interface[name=Ethernet1]/config/loopback-mode False
            /interfaces/interface[name=Ethernet1]/config/mtu 0
            /interfaces/interface[name=Ethernet1]/config/name Ethernet1
            <output-omitted>
        
        :param paths: List of paths
        :type paths: list
        :param options:
        :type options: gnmi.structures.GetOptions
        :rtype: gnmi.messages.SubscribeResponse_
        """
        aggregate = options.get("aggregate", False)
        encoding = util.get_gnmi_constant(options.get("encoding", "json"))
        heartbeat = options.get("heartbeat", None)
        interval = options.get("interval", None)
        mode = MODE_MAP.index(options.get("mode", "stream"))
        prefix = self._parse_path(options.get("prefix"))
        qos = pb.QOSMarking(marking=options.get("qos", 0))
        submode = util.get_gnmi_constant(options.get("submode") or "on-change")
        suppress = options.get("suppress", False)
        timeout = options.get("timeout", None)
        use_alias = options.get("use_alias", False)

        subs = []
        for path in paths:
            path = self._parse_path(path)
            sub = pb.Subscription(path=path, mode=submode,
                                  suppress_redundant=suppress,
                                  sample_interval=interval,
                                  heartbeat_interval=heartbeat)
            subs.append(sub)

        def _sr():

            sub_list = pb.SubscriptionList(prefix=prefix, mode=mode,
                                           allow_aggregation=aggregate,
                                           encoding=encoding, subscription=subs,
                                           use_aliases=use_alias, qos=qos)
            req_iter = pb.SubscribeRequest(subscribe=sub_list)
            yield req_iter

        try:
            responses = self._stub.Subscribe(
                _sr(), timeout, metadata=self.metadata)
            for response in responses:
                if response.HasField("sync_response"):
                    # TODO: notify the user about this?
                    continue
                elif response.HasField("update"):
                    yield SubscribeResponse_(response)
                else:
                    raise ValueError("Unknown response: " + str(response))

        except grpc.RpcError as rpcerr:
            status = Status_.from_call(rpcerr)

            if status.code.name == "DEADLINE_EXCEEDED":
                raise GrpcDeadlineExceeded(status)
            else:
                raise GrpcError(status)
