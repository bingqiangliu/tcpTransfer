#!/usr/bin/env python
from twisted.logger import Logger
from twisted.internet import reactor
from twisted.internet.protocol import ReconnectingClientFactory as RCFactory

import rtde.rtde as rtde
import rtde.rtde_config as rtde_config

ROBOT_ADDRESS = '192.168.100.1'
PORT = 30003


class PIProtocol(ModbusClientProtocol):
    log = Logger(namespace="PIProtocol")
    TRAVERSE_PREFIX = "T"
    TOUCH_PREFIX = "P"
    TOUCH_ADDRESS = 10

    def __init__(self):
        self.log.debug("beginning the processing loop")
        reactor.callLater(0, self.fetch_ur_status)

    @property
    def interval(self):
        return self.factory.interval / 1000

    @property
    def client(self):
        return self.factory.client

    def fetch_ur_stauts(self):
        #d = self.read_coils(self.TOUCH_ADDRESS, 1)
        d.addCallbacks(self.on_received_flag, self.error_handler)

    def send_traverse_points(self, response):
        registers = response.registers
        self.client.send("{},{},{},{}".format(self.TRAVERSE_PREFIX, *registers))
        self.log.info("start next cycle")
        reactor.callLater(self.interval, self.fetch_tcp_registers)

    def send_touch_points(self, response):
        registers = response.registers
        self.client.send("{},{},{},{}".format(self.TOUCH_PREFIX, *registers))
        self.reset_flag_register()
        reactor.callLater(self.interval * 2, self.fetch_flag_register)

    def error_handler(self, failure):
        self.log.error(str(failure))


class PIFactory(RCFactory):
    protocol = PIProtocol
    client = None
    interval = None
    running = False

    def __init__(self, client, interval):
        self.client = client
        self.interval = interval

    def startedConnecting(self, connector):
        self.running = True
        RCFactory.startedConnecting(self, connector)

    def clientConnectionFailed(self, connector, reason):
        self.running = False
        RCFactory.clientConnectionFailed(self, connector, reason)

    def clientConnectionLost(self, connector, unused_reason):
        self.running = False
        RCFactory.clientConnectionLost(self, connector, unused_reason)


class ModbusClient(object):
    log = Logger(namespace="ModbusClient")
    address = ROBOT_ADDRESS
    port = Defaults.Port
    client = None
    connector = None

    def __init__(self, client):
        self.client = client
        self.factory = PIFactory(self.client, 10)

    def reconfig(self, address, port=Defaults.Port):
        if (self.address, self.port) == (address, port):
            self.log.info("no configuration changed")
            return
        self.address, self.port = address, port
        self.log.info("config changed to {}".format((self.address, self.port)))

    def startPolling(self):
        if not self.factory.running and not self.connector:
            self.connector = reactor.connectTCP(self.address,
                                                self.port,
                                                self.factory)
            self.log.info("started reading position and translating to PI")

    def stopPolling(self):
        if self.factory.running and self.connector:
            self.connector.disconnect()
            self.connector = None
            self.log.info("stopped reading position and translating to PI")

