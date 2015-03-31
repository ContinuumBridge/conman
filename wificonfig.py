#!/usr/bin/env python
# wificonfig.py
# Copyright (C) ContinuumBridge Limited, 2013-2015 - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Peter Claydon
#
import sys
import time
import os
import json
import logging
from pprint import pprint
from twisted.internet import reactor
from twisted.application.internet import TCPServer
from twisted.application.service import Application
from twisted.web.resource import Resource
from twisted.web.server import Site
from twisted.internet.task import deferLater
from twisted.web.server import NOT_DONE_YET

ModuleName =                "WiFiConfig"
LOGFILE =                   "connections.log"
LOGGING_LEVEL =             logging.DEBUG

logging.basicConfig(filename=LOGFILE,level=LOGGING_LEVEL,format='%(asctime)s %(levelname)s: %(message)s')

class RootResource(Resource):
    isLeaf = True
    def __init__(self, htmlfile):
        logging.debug("%s RootResource", ModuleName)
        self.htmlfile = htmlfile
        Resource.__init__(self)

    def render_GET(self, request):
        logging.debug("%s render_GET", ModuleName)
        with open(self.htmlfile, 'r') as f:
            html = f.read()
        return html

    def render_POST(self, request):
        form = request.content.getvalue()
        if request.args["ssid"][0] != "": 
            print "Credentials = ", request.args["ssid"][0], request.args["wpa"][0]
        response = "<html><font size=7>Thank you. Trying to connect.</font></html>"
        return response

class WifiConfig():
    def __init__(self, argv):
        if len(argv) < 2:
            logging.error("%s cbAdaptor improper number of arguments", ModuleName)
            exit(1)
        htmlfile = argv[1]
        logging.info("%s Hello, html file: %s", ModuleName, htmlfile)
        reactor.listenTCP(80, Site(RootResource(htmlfile)))
        reactor.run()

    def stopReactor(self):
        try:
            reactor.stop()
        except:
            pass
            logging.debug("%s stop: reactor was not running", ModuleName)
        logging.info("%s Bye", ModuleName)
        sys.exit

if __name__ == '__main__':
    WifiConfig(sys.argv)
