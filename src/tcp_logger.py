#!/usr/bin/env python
from twisted.python import log
from twisted.python import logfile

def logger():
    f = logfile.LogFile("tcp.log", '/var/log/tcp/', rotateLength=10000000, maxRotatedFiles=50)
    log_observer = log.FileLogObserver(f)
    return log_observer.emit
