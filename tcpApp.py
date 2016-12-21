#!/usr/bin/env python
import sys
import os.path

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from app.mbclient import ModbusClient
from app.powerinspect import startServer
from twisted.application.internet import TCPServer
from twisted.application.service import Application
from twisted.web.resource import Resource
from twisted.web.server import Site


class Transfer(Resource):
    isLeaf = True

    def __init__(self, path):
        self.path = path
        self.piHandler = startServer(49000)
        self.mbClient = ModbusClient(self.piHandler)
        self.mbClient.startPolling()
        Resource.__init__(self)

    def render_GET(self, request):
        if self.mbClient.factory.running:
            return "Running"
        else:
            return "Stopped"

    def render_POST(self, _):
        self.mbClient.startPolling()
        return "Started"

    def render_PUT(self, _):
        self.mbClient.stopPolling()
        return "Stopped"


application = Application("UR TCP Transfer Application")
TCPServer(8880, Site(Transfer('/transfer'))).setServiceParent(application)
