#/usr/bin/env python
from twisted.web.server import Site
from twisted.web.resource import Resource
from twisted.application.service import Application
from twisted.application.internet import TCPServer

from sys import path
from os.path import abspath
from os.path import dirname 
path.append(abspath(dirname(__file__)))
from app.rtdeclient import RTDEClient
from app.powerinspect import startServer

class Transfer(Resource):
    isLeaf = True

    def __init__(self):
        self.piHandler = startServer(49000)
        self.exClient = RTDEClient(self.piHandler)
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
TCPServer(8880, Site(Transfer())).setServiceParent(application)
