#!/usr/bin/env python
from twisted.logger import Logger
from twisted.internet import reactor
from twisted.internet.task import LoopingCall
from twisted.internet.protocol import Factory
from twisted.internet.protocol import Protocol
from twisted.internet.endpoints import TCP4ServerEndpoint


class PowerInspect(Protocol):
    """Protocol between with PowerInspect.
    From the PowerInspect point of view, an assumption is once itself connected to one server, the server will continue
    send position back.
      The interval of packages back to PowerInspect is configurable, default is 10 milliseconds.
      It also has an interface for sending back any touch point position back any time.
    """
    log = Logger(namespace="PowerInspect")

    def __init__(self, factory):
        """returned protocol must have an attribute pointing to creating factory
        REF: http://twistedmatrix.com/documents/current/api/twisted.internet.protocol.Factory.html#buildProtocol
        """
        self.factory = factory

    def connectionMade(self):
        """Once a connection is made, fire loop"""
        self.log.info("Connection made")

    def connectionLost(self, transport):
        """Stop to looping task"""
        self.log.info("Connection lost {}".format(transport))


class PowerInspectFactory(Factory):
    """Factory for PowerInspect protocol.
    The whole reason why we need a factory is because sending touch point position is not predicative, so we should
    have a protocol instance handle for calling its interface.
    """
    log = Logger(namespace="PowerInspectFactory")
    connections = None

    def __init__(self):
        self.connections = []

    def buildProtocol(self, address):
        self.log.debug("Build protocol for {}".format(address))
        pi = PowerInspect(self)
        self.connections.append(pi)
        return pi

    def stopFactory(self):
        """Clear all protocol"""
        for connection in self.connections:
            connection.transport.loseConnection()
        self.connections[:] = []

    def send(self, data):
        """Send data back to all clients"""
        self.log.debug("Sending {} back to all clients".format(data))
        for connection in self.connections:
            connection.transport.send(data)


_server = None
_interface = None
_pihandler = None
log = Logger(namespace="PIServer")


def startServer(port):
    global _server, _pihandler
    if _server is None or _server.config != port:
        _server = TCP4ServerEndpoint(reactor, port)
        _server.config = port
        log.info("Server started and is listening on {}".format(_server.config))
        _pihandler = PowerInspectFactory()
        d = _server.listen(_pihandler)

        def got(inst):
            global _interface
            _interface = inst
        def err(reason):
            log.error(reason)
        d.addCallbacks(got)
        d.addErrback(err)
    else:
        _server.config = port
        log.info("Server refreshed and is listening on {}".format(_server.config))
        _interface.startListening()
    return _pihandler


def stopServer():
    _interface.stopListening()
    log.info("Server stopped")
