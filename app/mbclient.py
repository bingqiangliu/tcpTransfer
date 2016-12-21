#!/usr/bin/env python
from twisted.logger import Logger
from twisted.internet import reactor
from twisted.internet.protocol import ReconnectingClientFactory as RCFactory

from pymodbus.constants import Defaults
from pymodbus.client.async import ModbusClientProtocol

ROBOT_ADDRESS = '192.168.100.1'

class PIProtocol(ModbusClientProtocol):
    log = Logger(namespace="PIProtocol")
    TRAVERSE_PREFIX = "T"
    TOUCH_PREFIX = "P"
    TCP_ADDRESS = 400
    TOUCH_ADDRESS = 1

    def __init__(self, framer=None):
        ModbusClientProtocol.__init__(self, framer=framer)
        self.log.debug("beginning the processing loop")
        reactor.callLater(0, self.fetch_tcp_registers)
        reactor.callLater(0, self.fetch_flag_register)

    @property
    def interval(self):
        return self.factory.interval / 1000

    @property
    def client(self):
        return self.factory.client

    def fetch_flag_register(self):
        d = self.read_coils(self.TOUCH_ADDRESS, 1)
        d.addCallbacks(self.on_received_flag, self.error_handler)

    def on_received_flag(self, response):
        flag = True if response.getBit(0) else False
        if flag:
            self.log.info("touch happened")
            reactor.callLater(0, self.fetch_tcp_registers, True)
        else:
            self.log.info("start next cycle for touched")
            reactor.callLater(self.interval * 2, self.fetch_flag_register)

    def fetch_tcp_registers(self, touched=False):
        self.log.debug("fetching TCP registers touched={}".format(touched))
        d = self.read_holding_registers(self.TCP_ADDRESS, 3)
        if touched:
            d.addCallbacks(self.send_touch_points, self.error_handler)
        else:
            d.addCallbacks(self.send_traverse_points, self.error_handler)

    def send_traverse_points(self, response):
        registers = response.registers
        self.client.send("{},{},{},{}".format(self.TRAVERSE_PREFIX, *registers))
        self.log.info("start next cycle")
        reactor.callLater(self.interval, self.fetch_tcp_registers)

    def send_touch_points(self, response):
        registers = response.registers
        self.client.send("{},{},{},{}".format(self.TOUCH_PREFIX, *registers))
        self.reset_flag_register()

    def reset_flag_register(self):
        self.log.debug("reset flag register")

        def done(response):
            self.log.info("reset succeed {}, start next cycle".
                          format(response))
            reactor.callLater(self.interval * 2, self.fetch_flag_register)

        def error(failure):
            self.log.error("reset failed {}, retry".format(str(failure)))
            reactor.callLater(self.interval / 2, self.reset_flag_register)

        d = self.write_coil(self.TOUCH_ADDRESS, False)
        d.addCallbacks(done, error)

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

