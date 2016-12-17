#!/usr/bin/env python

from app.mbclient import MbClient
from app.powerinspect import stopServer
from app.powerinspect import startServer
from twisted.application.internet import TCPServer
from twisted.application.service import Application
from twisted.web.resource import Resource
from twisted.web.server import Site


class Transfer(Resource):
    isLeaf = True

    def __init__(self, path):
        self.path = path
        self.piHandler = startServer(9999)
        self.mbClient = MbClient(self.piHandler)
        self.mbClient.reconfig('127.0.0.1', 5020)
        Resource.__init__(self)

    def render_GET(self, request):
        if self.mbClient.factory.running:
            return "Running"
        else:
            return "Stopped"

    def render_POST(self, request):
        self.mbClient.startPolling()
        return "Started"

    def render_PUT(self, request):
        self.mbClient.stopPolling()
        return "Stopped"


application = Application("UR TCP Transfer Application")
TCPServer(8880, Site(Transfer('/transfer'))).setServiceParent(application)
