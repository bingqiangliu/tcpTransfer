#!/usr/bin/env python
import sys
import os.path

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from app.rtdeclient import RTDEClient
from app.powerinspect import startServer
from twisted.application.internet import TCPServer
from twisted.application.service import Application
from twisted.web.resource import Resource
from twisted.web.server import Site


class Transfer(Resource):
    isLeaf = True

    def __init__(self):
        self.piHandler = startServer(49000)
        self.exClient = RTDEClient(self.piHandler)
        self.exClient.startPolling()
        Resource.__init__(self)

    def render_GET(self, request):
        if self.exClient.factory.running:
            return "Running"
        else:
            return "Stopped"

    def render_POST(self, _):
        self.exClient.startPolling()
        return "Started"

    def render_PUT(self, _):
        self.exClient.stopPolling()
        return "Stopped"


application = Application("UR TCP Transfer Application")
TCPServer(8880, Site(Transfer('/transfer'))).setServiceParent(application)
