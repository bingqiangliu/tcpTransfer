#!/usr/bin/env python
from twisted.logger import Logger
from twisted.internet import reactor
from zope.interface import Interface
from zope.interface import implements
from twisted.internet.protocol import Factory
from twisted.internet.protocol import Protocol
from twisted.internet.protocol import connectionDone
from txgpio.sysfs import GPIO


class SysfsGPIOProtocol(Protocol):
    log = Logger(namespace="SysfsGPIOProtocol")

    def connectionMade(self):
        self.log.msg('Connection is made')
        self.factory.connected = True

    def dataReceived(self, data):
        self.factory.on_receive(data)

    def connectionLost(self, reason=connectionDone):
        self.log.msg('Connection is lost')
        self.factory.connected = False


class ISysfsGPIOFactory(Interface):
    def on_receive(self, data):
        pass


class SysfsGPIOFactory(Factory):
    implements(ISysfsGPIOFactory)

    log = Logger(namespace="SysfsGPIOFactory")
    protocol = SysfsGPIOProtocol
    connected = False
    receiveHandler = None

    def __init__(self, receiveHandler):
        self.receiveHandler = receiveHandler

    def on_receive(self, data):
        self.log.msg('Read value: {}'.format(data))
        self.receiveHandler.onReceived()


def registerGPIO(recieveHandler):
    factory = SysfsGPIOFactory(recieveHandler)
    GPIO(factory.buildProtocol(None),
         reactor=reactor,
         gpio_no='',
         direction='in',
         edge='[none, rising, falling, both]',
         active_low='0 or 1')
