#/usr/bin/env python
import os
from twisted.logger import Logger
from twisted.web.server import Site
from twisted.web.static import File
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
    logger = Logger('API')

    def __init__(self):
        self.piHandler = startServer(49000)
        self.exClient = RTDEClient(self.piHandler)
        self.path = "api"
        if "TCPRUN" in os.environ:
            self.exClient.startPolling()

    def render_GET(self, _):
        self.logger.info('render_GET current running={}'.format(self.exClient.factory.running))
        return str(self.exClient.factory.running)

    def render_POST(self, request):
        action = request.args['action'][0]
        self.logger.info('render POST action={} current running={}'.format(action, self.exClient.factory.running))
        if action == 'start' and not self.exClient.factory.running:
            self.exClient.startPolling()
        elif action == 'stop' and self.exClient.factory.running:
            self.exClient.stopPolling()
        return True


class WebUI(Resource):
    logger = Logger('WebUI')

    def __init__(self):
        self.api = API()
        Resource.__init__(self)
        self.putChild("api", self.api)
	self.putChild("log", File('/var/log/tcp/tcp.log', defaultType='html'))

    def getChild(self, path, request):
        return self

    def render_POST(self, request):
        return self.render_GET(request)

    def render_GET(self, _):
        status, text, action = None, None, None
        if self.api.exClient.factory.running:
            status, text, action = "Running", "Stop", "stop"
        else:
            status, text, action = "Stopped", "Start", "start"

        return """
            <HTML>
            <HEAD>
            <META http-equiv="refresh" content="15" />
            <TITLE>Touch Point Monitor Application</TITLE>
            </HEAD>
            <BODY>
            <H1>{}</H1>
            <FORM method="post">
                <BUTTON type="submit" name="action" value="{}" >{}</BUTTON>
            </FORM>
            </BODY>
            </HTML>
                """.format(status, action, text)


application = Application("UR TCP Transfer Application")
TCPServer(80, Site(WebUI())).setServiceParent(application)
