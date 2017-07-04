#!/usr/bin/env python
import twisted.python.logfile

def logger():
    f = logfile.LogFile("tcp.log", '/var/log/tcp/', rotateLength=10000000, maxRotatedFiles=50)
    log_observer = log.FileLogObserver(f)
    return log_observer.emit
