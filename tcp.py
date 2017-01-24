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


class API(Resource):
    isLeaf = True

    def __init__(self):
        self.piHandler = startServer(49000)
        self.exClient = RTDEClient(self.piHandler)
        Resource.__init__(self)

    def render_GET(self, _):
        status, text = ("Running", "Start") if self.exClient.factory.running else ("Stopped", "Stop")

        return """
            <HTML>
            <HEAD>
            <META http-equiv="refresh" content="5" />
            <TITLE>Touch Point Monitor Application</TITLE>
            </HEAD>
            <BODY>
            <H1>{}</H1>
            <FORM action="api" method="post">
                <INPUT type="submit" value="Start">
            </FORM>
            </BODY>
            </HTML>
                """.format(status, text)

    def render_POST(self, _):
        self.exClient.startPolling()
        return True

    def render_PUT(self, _):
        self.exClient.stopPolling()
        return True


application = Application("UR TCP Transfer Application")
TCPServer(8880, Site(API())).setServiceParent(application)
