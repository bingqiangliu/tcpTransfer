#!/usr/bin/env python
from twisted.logger import Logger
from twisted.internet import reactor
from twisted.internet.protocol import ReconnectingClientFactory as RCFactory

from rtde.rtde import RTDE

ROBOT_ADDRESS = '192.168.1.2'
PORT = 30004


class RTDEFactory(RCFactory):
    protocol = RTDE
    client = None
    running = False

    def __init__(self, client):
        self.client = client

    def startedConnecting(self, connector):
        self.running = True
        RCFactory.startedConnecting(self, connector)

    def clientConnectionFailed(self, connector, reason):
        self.running = False
        RCFactory.clientConnectionFailed(self, connector, reason)

    def clientConnectionLost(self, connector, unused_reason):
        self.running = False
        RCFactory.clientConnectionLost(self, connector, unused_reason)


class RTDEClient(object):
    log = Logger(namespace="RTDEClient")
    client = None
    connector = None

    def __init__(self, client):
        self.client = client
        self.factory = RTDEFactory(self.client)

    def reconfig(self, address):
        if self.address == address:
            self.log.info("no configuration changed")
            return
        self.address = address
        self.log.info("config changed to {}".format(self.address))

    def startPolling(self):
        if not self.factory.running and not self.connector:
            self.connector = reactor.connectTCP(ROBOT_ADDRESS, PORT, self.factory)
            self.log.info("started reading position and translating to PI")

    def stopPolling(self):
        if self.factory.running and self.connector:
            self.connector.disconnect()
            self.connector = None
            self.log.info("stopped reading position and translating to PI")

