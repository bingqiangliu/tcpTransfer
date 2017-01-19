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
from twisted.logger import Logger
from twisted.internet import reactor
from twisted.internet.protocol import Factory
from twisted.internet.protocol import Protocol
from twisted.internet.endpoints import TCP4ServerEndpoint

import serialize

RTDE_PROTOCOL_VERSION = 1
DEFAULT_TIMEOUT = 1.0

class Command:
    RTDE_REQUEST_PROTOCOL_VERSION = 86        # ascii V
    RTDE_GET_URCONTROL_VERSION = 118          # ascii v
    RTDE_TEXT_MESSAGE = 77                    # ascii M
    RTDE_DATA_PACKAGE = 85                    # ascii U
    RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS = 79   # ascii O
    RTDE_CONTROL_PACKAGE_SETUP_INPUTS = 73    # ascii I
    RTDE_CONTROL_PACKAGE_START = 83           # ascii S
    RTDE_CONTROL_PACKAGE_PAUSE = 80           # ascii P


class ConnectionState:
    DISCONNECTED = 0
    CONNECTED = 1
    STARTED = 2


class RTDE(Protocol):
    """RTDE sequence is as following
        1. Check controller version (>=3.2.19171)
        2. Negotiate RTDE protocol version (current 1)
        3. Setup favourite output
        4. Recieve looping output
    """
    log = Logger(namespace="RTDE")

    def __init__(self):
        self.__conn_state = ConnectionState.DISCONNECTED
        self.__output_config = None
        self.__cmd = None
        self.__buf = ''

    def connectionMade(self):
        self.__conn_state = ConnectionState.CONNECTED
        self.get_controller_version()

    def dataReceived(self, data):
        """spin according to cmd"""
        self.__buf += data
        # unpack_from requires a buffer of at least 3 bytes
        while len(self.__buf) >= 3:
            # Attempts to extract a packet
            packet_header = serialize.ControlHeader.unpack(self.__buf)

            if len(self.__buf) >= packet_header.size:
                packet, self.__buf = self.__buf[3:packet_header.size], self.__buf[packet_header.size:]
                content = self.__on_packet(packet_header.command, packet)
                if packet_header.command == self.__command:
                    #switch
                else:
                    #not what we expect, just skip
                    pass
            else:
                break

    def on_controller_version(self, data):
        """check version"""
        v = self.__sendAndReceive(cmd)
        if not v:
            return None
        self.log.info('Controller version: {}.{}.{}.{}'.format(v.major, v.minor, v.bugfix, v.build))
        if v.major == 3 and v.minor <= 2 and v.bugfix < 19171:
            self.log.error("Please upgrade your controller to minimally version 3.2.19171")
            sys.exit()

    def get_controller_version(self):
        self.__cmd = Command.RTDE_GET_URCONTROL_VERSION
        self.__send()

    def negotiate_protocol_version(self):
        self.__cmd = Command.RTDE_REQUEST_PROTOCOL_VERSION
        payload = struct.pack('>H', RTDE_PROTOCOL_VERSION )
        self.__send(payload)

    def on_protocol_version(self, data):
        if data == RTDE_PROTOCOL_VERSION:
            pass

    def send_output_setup(self, variables, types=[]):
        self.__cmd = Command.RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS
        payload = ','.join(variables)
        self.__send(payload)

    def on_output_setup(self, data):
        result = self.__sendAndReceive(cmd, payload)
        if len(types)!=0 and not self.__list_equals(result.types, types):
            logging.error('Data type inconsistency for output setup: ' +
                     str(types) + ' - ' +
                     str(result.types))
            return False
        result.names = variables
        self.__output_config = result
        return True

    def send_start(self):
        self.__cmd = Command.RTDE_CONTROL_PACKAGE_START
        self.__send()

    def on_start(self, data):
        success = self.__sendAndReceive(cmd)
        if success:
            self.log.info('RTDE synchronization started')
            self.__conn_state = ConnectionState.STARTED
        else:
            self.log.error('RTDE synchronization failed to start')
        return success

    def receive(self):
        if self.__output_config is None:
            logging.error('Output configuration not initialized')
            return None
        if self.__conn_state != ConnectionState.STARTED:
            logging.error('Cannot receive when RTDE synchronization is inactive')
            return None
        return self.__recv(Command.RTDE_DATA_PACKAGE)

    def __on_packet(self, cmd, payload):
        if cmd == Command.RTDE_REQUEST_PROTOCOL_VERSION:
            return self.__unpack_protocol_version_package(payload)
        elif cmd == Command.RTDE_GET_URCONTROL_VERSION:
            return self.__unpack_urcontrol_version_package(payload)
        elif cmd == Command.RTDE_TEXT_MESSAGE:
            return self.__unpack_text_message(payload)
        elif cmd == Command.RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS:
            return self.__unpack_setup_outputs_package(payload)
        elif cmd == Command.RTDE_CONTROL_PACKAGE_START:
            return self.__unpack_start_package(payload)
        elif cmd == Command.RTDE_DATA_PACKAGE:
            return self.__unpack_data_package(payload, self.__output_config)
        else:
            logging.error('Unknown package command: ' + str(cmd))


    def __send(self, payload=''):
        fmt = '>HB'
        size = struct.calcsize(fmt) + len(payload)
        buf = struct.pack(fmt, size, self.__cmd) + payload
        self.transport.write(buf)

    def __unpack_protocol_version_package(self, payload):
        if len(payload) != 1:
            logging.error('RTDE_REQUEST_PROTOCOL_VERSION: Wrong payload size')
            return None
        result = serialize.ReturnValue.unpack(payload)
        return result.success

    def __unpack_urcontrol_version_package(self, payload):
        if len(payload) != 16:
            logging.error('RTDE_GET_URCONTROL_VERSION: Wrong payload size')
            return None
        version = serialize.ControlVersion.unpack(payload)
        return version

    def __unpack_text_message(self, payload):
        if len(payload) < 1:
            logging.error('RTDE_TEXT_MESSAGE: No payload')
            return None
        msg = serialize.Message.unpack(payload)
        if(msg.level == serialize.Message.EXCEPTION_MESSAGE or 
           msg.level == serialize.Message.ERROR_MESSAGE):
            logging.error('Server message: ' + msg.message)
        elif msg.level == serialize.Message.WARNING_MESSAGE:
            logging.warning('Server message: ' + msg.message)
        elif msg.level == serialize.Message.INFO_MESSAGE:
            logging.info('Server message: ' + msg.message)

    def __unpack_setup_outputs_package(self, payload):
        if len(payload) < 1:
            logging.error('RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS: No payload')
            return None
        return serialize.DataConfig.unpack_recipe(payload, False)

    def __unpack_start_package(self, payload):
        if len(payload) != 1:
            logging.error('RTDE_CONTROL_PACKAGE_START: Wrong payload size')
            return None
        result = serialize.ReturnValue.unpack(payload)
        return result.success

    def __unpack_data_package(self, payload, output_config):
        if output_config is None:
            logging.error('RTDE_DATA_PACKAGE: Missing output configuration')
            return None
        output = output_config.unpack(payload)
        return output

    def __list_equals(self, l1, l2):
        if len(l1) != len(l2):
            return False
        for i in range(len((l1))):
            if l1[i] != l2[i]:
                return False
        return True

