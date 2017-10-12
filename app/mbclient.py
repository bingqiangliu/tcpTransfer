#!/usr/bin/env python
from twisted.logger import Logger
from twisted.internet import reactor
from twisted.internet.protocol import ReconnectingClientFactory as RCFactory

from pymodbus.constants import Endian
from pymodbus.constants import Defaults
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.client.async import ModbusClientProtocol

ROBOT_ADDRESS = '192.168.0.2'

class PIProtocol(ModbusClientProtocol):
    log = Logger(namespace="PIProtocol")
    TRAVERSE_PREFIX = "T"
    TOUCH_PREFIX = "P"

    def __init__(self, framer=None):
        ModbusClientProtocol.__init__(self, framer=framer)
        self.log.debug("beginning the processing loop")
        reactor.callLater(0, self.fetch_tcp_registers)
        reactor.callLater(0, self.fetch_flag_register)
        self.previous_touched = False

    @property
    def interval(self):
        return self.factory.interval / 1000

    @property
    def interval_after_touched(self):
        return self.factory.interval_after_touched / 1000

    @property
    def client(self):
        return self.factory.client

    def fetch_flag_register(self):
        """TM specification:
        |-----------|----|-------------|-------------|------|----|
        |End Module | FC | Address Dec | Address Hex | Type | R/W|
        |-----------|----|-------------|-------------|------|----|
        |DI 0      | 02 | 0800        | 0320        | Bool | R  |
        |DI 1      | 02 | 0801        | 0321        | Bool | R  |
        |-----------|----|-------------|-------------|------|----|
        DI 0 is used to store touch point flag.
        Value of DI 0 is always 1 if no touch, changes to 0 while touching

        """
        d = self.read_discrete_inputs(800, 1)
        d.addCallbacks(self.on_received_flag, self.error_handler)

    def on_received_flag(self, response):
        flag = True if response.getBit(0) else False
        if not flag:
            self.log.info("touch happened")
            if self.previous_touched:
                self.log.info("previous touched is True, skip continus touch point signal")
                self.log.info("start next cycle to fetch flag")
                reactor.callLater(self.interval * 2, self.fetch_flag_register)
                return
            self.previous_touched = True
            reactor.callLater(self.interval_after_touched, self.fetch_tcp_registers, True)
        else:
            self.log.info("start next cycle for touched")
            self.previous_touched = False
            reactor.callLater(self.interval * 2, self.fetch_flag_register)

    def fetch_tcp_registers(self, touched=False):
        """TM specification:
        |-----------------|----|-------------|-------------|------|-----|------|
        |Robot Coordinate | FC | Address Dec | Address Hex | Type | R/W | Note |
        |-----------------|----|-------------|-------------|------|-----|------|
        |X(Cartesian coor | 04 | 7025 ~ 7026 | 1B71 ~ 1B72 | Float| R   | Dword|
        |Y(Cartesian coor | 04 | 7027 ~ 7028 | 1B73 ~ 1B74 | Float| R   | Dword|
        |Z(Cartesian coor | 04 | 7029 ~ 7030 | 1B75 ~ 1B76 | Float| R   | Dword|
        |-----------------|----|-------------|-------------|------|-----|------|
        7425 ~ 7430 will be set after touched for the same XYZ
        Order : ABCD -> ABCD BigEndian
        """
        self.log.debug("fetching TCP registers touched={}".format(touched))
        if touched:
            d = self.read_input_registers(7425, 6)
            d.addCallbacks(self.send_touch_points, self.error_handler)
        else:
            d = self.read_input_registers(7025, 6)
            d.addCallbacks(self.send_traverse_points, self.error_handler)

    def send_traverse_points(self, response):
        registers = response.registers
        x, y, z = self.decode_xyz(registers)
        self.client.send("{},{},{},{}".format(self.TRAVERSE_PREFIX, *(x, y, z)))
        self.log.info("start next cycle to fetch tcp")
        reactor.callLater(self.interval, self.fetch_tcp_registers)

    def send_touch_points(self, response):
        registers = response.registers
        x, y, z = self.decode_xyz(registers)
        self.client.send("{},{},{},{}".format(self.TOUCH_PREFIX, *(x, y, z)))
        self.log.info("start next cycle to fetch flag")
        reactor.callLater(self.interval * 2, self.fetch_flag_register)

    def decode_xyz(self, payload):
        def registers_to_str(r):
            h = (r >> 8) & 0xff
            l = r & 0xff
            return "{}{}".format(chr(h), chr(l))

        self.log.info('original payload ={}'.format(payload))
        str_payload = "{}{}{}{}{}{}".format(
            registers_to_str(payload[0]),
            registers_to_str(payload[1]),
            registers_to_str(payload[2]),
            registers_to_str(payload[3]),
            registers_to_str(payload[4]),
            registers_to_str(payload[5])
        )
        decoder = BinaryPayloadDecoder(str_payload, endian=Endian.Big)
        x = decoder.decode_32bit_float()
        y = decoder.decode_32bit_float()
        z = decoder.decode_32bit_float()
        self.log.info('x={}, y={}, z={}'.format(x, y, z))
        return (x, y, z)

    def error_handler(self, failure):
        self.log.error(str(failure))


class PIFactory(RCFactory):
    protocol = PIProtocol
    client = None
    interval = None
    interval_after_touched = None
    running = False

    def __init__(self, client, interval, interval_after_touched):
        self.client = client
        self.interval = interval
        self.interval_after_touched  = interval_after_touched

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
        self.factory = PIFactory(self.client, 1, 30)

    def reconfig(self, address, port=Defaults.Port):
        if (self.address, self.port) == (address, port):
            self.log.info("no configuration changed")
            return
        self.address, self.port = address, port
        self.log.info("config changed to {}".format((self.address, self.port)))

    def startPolling(self):
        if not self.factory.running and not self.connector:
            self.log.info("try to start reading position and translating to PI")
            self.connector = reactor.connectTCP(self.address,
                                                self.port,
                                                self.factory)

    def stopPolling(self):
        if self.factory.running and self.connector:
            self.connector.disconnect()
            self.connector = None
            self.log.info("stopped reading position and translating to PI")

