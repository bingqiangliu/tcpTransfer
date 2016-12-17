#!/usr/bin/env python
from twisted.logger import Logger
from twisted.internet import reactor
from twisted.internet.protocol import ReconnectingClientFactory
from pymodbus.constants import Defaults
from pymodbus.client.sync import ModbusTcpClient
from pymodbus.client.async import ModbusClientProtocol


class PIProtocol(ModbusClientProtocol):
    log = Logger(namespace="ModbusClientProtocol")
    PREFIX = "T"

    def __init__(self, framer=None):
        ''' Initializes our custom protocol

        :param framer: The decoder to use to process messages
        :param endpoint: The endpoint to send results to
        '''
        ModbusClientProtocol.__init__(self, framer=None)
        self.log.debug("Beginning the processing loop")
        #reactor.callLater(self.factory.interval / 1000, self.fetch_holding_registers)

    def fetch_holding_registers(self):
        ''' Defer fetching holding registers
        '''
        self.log.debug("Starting the next cycle")
        #d = self.read_holding_registers(*STATUS_REGS)
        #d.addCallbacks(self.send_holding_registers, self.error_handler)

    def send_holding_registers(self, response):
        ''' Write values of holding registers, defer fetching coils

        :param response: The response to process
        '''
        #TODO: send data back to PowerInsepct after reform

        self.start_next_cycle()

    def start_next_cycle(self):
        ''' Write values of coils, trigger next cycle

        :param response: The response to process
        '''
        reactor.callLater(self.factory.interval / 1000, self.fetch_holding_registers)

    def error_handler(self, failure):
        ''' Handle any twisted errors

        :param failure: The error to handle
        '''
        self.log.error(failure)


class PIFactory(ReconnectingClientFactory):
    protocol = PIProtocol
    piHandler = None
    interval = None
    running = False

    def __init__(self, piHandler, interval):
        self.piHandler = piHandler
        self.interval = interval

    def startedConnecting(self, connector):
        self.running = True
        ReconnectingClientFactory.startedConnecting(self, connector)

    def clientConnectionFailed(self, connector, reason):
        self.running = False
        ReconnectingClientFactory.clientConnectionFailed(self, connector, reason)

    def clientConnectionLost(self, connector, unused_reason):
        self.running = False
        ReconnectingClientFactory.clientConnectionLost(self, connector, unused_reason)


class MbClient(object):
    """client to handle polling and event processing"""
    log = Logger(namespace="ModbusClient")
    address = None
    port = None
    piHandler = None
    connector = None

    def __init__(self, piHandler):
        self.piHandler = piHandler
        self.factory = PIFactory(self.piHandler, 10)

    def reconfig(self, address, port=Defaults.Port):
        """reconfig address and/or port"""
        if (self.address, self.port) == (address, port):
            self.log.info("no configuration changed")
            return
        #stop polling and re-construct clients
        self.address, self.port = address, port

    def startPolling(self):
        """start polling"""
        if not self.factory.running and not self.connector:
            self.log.info("start reading TCP of moving point and translating to PI")
            self.connector = reactor.connectTCP(self.address, self.port, self.factory)

    def stopPolling(self):
        """stop polling"""
        if self.factory.running and self.connector:
            self.log.info("stop reading TCP of moving point and translating to PI")
            self.connector.disconnect()
            self.connector = None

    def eventHandler(self):
        """read and transfer to PI synchronously"""
        try:
            self.stopPolling()
            with ModbusTcpClient(self.address, self.port) as cli:
                #TODO: complete command sending and result parser
                result = cli.execute('')
                #add "P" prefix
                self.piHandler.send(result)
        except Exception as error:
            self.log.error(str(error))
        finally:
            self.startPolling()

