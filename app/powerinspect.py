#!/usr/bin/env python
from twisted.logger import Logger
from twisted.internet import reactor
from twisted.internet.protocol import Factory
from twisted.internet.protocol import Protocol
from twisted.internet.endpoints import TCP4ServerEndpoint


class PowerInspect(Protocol):
    log = Logger(namespace="PowerInspect")

    def __init__(self, factory):
        self.factory = factory

    def connectionMade(self):
        self.log.info("connection made")

    def connectionLost(self, transport):
        self.log.info("connection lost")


class PowerInspectFactory(Factory):
    log = Logger(namespace="PowerInspectFactory")
    connections = None

    def __init__(self):
        self.connections = []

    def buildProtocol(self, address):
        self.log.debug("build protocol for {}".format(address))
        pi = PowerInspect(self)
        self.connections.append(pi)
        return pi

    def stopFactory(self):
        for connection in self.connections:
            connection.transport.loseConnection()
        self.connections[:] = []

    def send(self, data):
        #self.log.debug("sending {} back to all clients".format(data))
        for connection in self.connections:
            connection.transport.write("{}\n".format(data))


_server = None
_interface = None
_pihandler = None
log = Logger(namespace="PIServer")


def startServer(port):
    global _server, _pihandler
    if _server is None or _server.config != port:
        _server = TCP4ServerEndpoint(reactor, port)
        _server.config = port
        log.info("server start to listen on {}".format(_server.config))
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
        log.info("server restart to listen on {}".format(_server.config))
        _interface.startListening()
    return _pihandler


def stopServer():
    _interface.stopListening()
    log.info("server stopped")
