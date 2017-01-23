# Copyright (c) 2016, Universal Robots A/S,
# All rights reserved.
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#    * Neither the name of the Universal Robots A/S nor the names of its
#      contributors may be used to endorse or promote products derived
#      from this software without specific prior written permission.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL UNIVERSAL ROBOTS A/S BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


import struct
from os.path import join
from os.path import abspath
from os.path import dirname
from twisted.logger import Logger
from twisted.internet.protocol import Protocol
import serialize
from rtde_config import ConfigFile


TRAVERSE_PREFIX = "T"
TOUCH_PREFIX = "P"
PROTOCOL_VERSION = 1
DEFAULT_TIMEOUT = 1.0
CONFIG_FILE = join(dirname(abspath(__file__)), 'configuration.xml')


class Command:
    REQUEST_PROTOCOL_VERSION = 86        # ascii V
    GET_URCONTROL_VERSION = 118          # ascii v
    DATA_PACKAGE = 85                    # ascii U
    CONTROL_PACKAGE_SETUP_OUTPUTS = 79   # ascii O
    CONTROL_PACKAGE_START = 83           # ascii S

class RTDE(Protocol):
    """RTDE sequence is as following
        1. Check controller version (>=3.2.19171)
        2. Negotiate RTDE protocol version (current 1)
        3. Setup favourite output
        4. Receive looping output
    """
    log = Logger(namespace="RTDE")


    @property
    def client(self):
        return self.factory.client

    def __init__(self):
        self.log.debug("beginning the processing loop")
        self.__names, self.__types = ConfigFile(CONFIG_FILE).get_recipe('transfer')
        self.__config = None
        self.__cmd = None
        self.buf = ''

    def connectionMade(self):
        """kick off sequence as soon as socket connection made"""
        self.get_control_version()

    def dataReceived(self, data):
        """spin according to cmd code"""
        self.buf += data
        # unpack_from requires a buffer of at least 3 bytes
        while len(self.buf) >= 3:
            # Attempts to extract a packet
            packet_header = serialize.ControlHeader.unpack(self.buf)

            if len(self.buf) >= packet_header.size:
                payload, self.buf = self.buf[3:packet_header.size], self.buf[packet_header.size:]
                if packet_header.command != self.__cmd:
                    self.log.error("Expected cmd {}, but got {}. Skip it!".format(self.__cmd, packet_header.command))
                    continue
                self.__on_packet(payload)
            else:
                break

    def get_control_version(self):
        self.__send(Command.GET_URCONTROL_VERSION)

    def check_control_version(self, payload):
        if len(payload) != 16:
            raise Exception("GET_URCONTROL_VERSION: Wrong payload size")
        ver = serialize.ControlVersion.unpack(payload)
        if not ver:
            raise Exception("GET_URCONTROL_VERSION: Empty payload")
        if ver.major == 3 and ver.minor <= 2 and ver.bugfix < 19171:
            ver_str = '{}.{}.{}.{}'.format(ver.major, ver.minor, ver.bugfix, ver.build)
            raise Exception("GET_URCONTROL_VERSION: {} not support".format(ver_str))

        self.request_protocol_version()

    def request_protocol_version(self):
        payload = struct.pack('>H', PROTOCOL_VERSION)
        self.__send(Command.REQUEST_PROTOCOL_VERSION, payload)

    def check_protocol_version(self, payload):
        if len(payload) != 1:
            raise Exception('REQUEST_PROTOCOL_VERSION: Wrong payload size')
        result = serialize.ReturnValue.unpack(payload)
        if not result.success:
            raise Exception('REQUEST_PROTOCOL_VERSION: Negotiation failed')

        self.setup_output()

    def setup_output(self):
        payload = ','.join(self.__names)
        self.__send(Command.CONTROL_PACKAGE_SETUP_OUTPUTS, payload)

    def check_output_setup(self, payload):
        if len(payload) < 1:
            raise Exception('CONTROL_PACKAGE_SETUP_OUTPUTS: No payload')
        config = serialize.DataConfig.unpack_recipe(payload, False)
        if not RTDE.__cmp(config.types, self.__types):
            raise Exception('Data type inconsistency for output setup: {}-{}'.format(self.__types, config.types))
        config.names = self.__names
        self.__config = config

        self.start()

    def start(self):
        self.__send(Command.CONTROL_PACKAGE_START)

    def check_start(self, payload):
        if len(payload) != 1:
            raise Exception('CONTROL_PACKAGE_START: Wrong payload size')
        result = serialize.ReturnValue.unpack(payload)
        if not result.success:
            raise Exception('CONTROL_PACKAGE_START: Start failed')

        self.__cmd = Command.DATA_PACKAGE

    def data_received(self, payload):
        output = self.__config.unpack(payload)
        x, y, z = output.actual_TCP_pose[:3]
	flag = output.actual_digital_input_bits
        self.client.send("{},{},{},{}".format(TRAVERSE_PREFIX if flag else TOUCH_PREFIX, x * 1000, y * 1000, z * 1000))

    def __on_packet(self, payload):
        if self.__cmd == Command.REQUEST_PROTOCOL_VERSION:
            self.check_protocol_version(payload)
        elif self.__cmd == Command.GET_URCONTROL_VERSION:
            self.check_control_version(payload)
        elif self.__cmd == Command.CONTROL_PACKAGE_SETUP_OUTPUTS:
            self.check_output_setup(payload)
        elif self.__cmd == Command.CONTROL_PACKAGE_START:
            self.check_start(payload)
        elif self.__cmd == Command.DATA_PACKAGE:
            self.data_received(payload)
        else:
            self.log.error('Should not be here')

    def __send(self, cmd, payload=''):
        self.__cmd, fmt = cmd, '>HB'
        size = struct.calcsize(fmt) + len(payload)
        buf = struct.pack(fmt, size, cmd) + payload
        self.transport.write(buf)

    @staticmethod
    def __cmp(l1, l2):
        if len(l1) != len(l2):
            return False
        for i in range(len((l1))):
            if l1[i] != l2[i]:
                return False
        return True

