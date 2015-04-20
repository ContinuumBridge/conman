#!/usr/bin/env python
# conman.py
# Copyright (C) ContinuumBridge Limited, 2014-2015 All Rights Reserved
# Written by Peter Claydon
#
import sys
import time
import os
import signal
from subprocess import call, check_output
import pexpect
import logging
from twisted.internet import threads
from twisted.internet import reactor, defer

ModuleName =                "conman"
PING_TIMEOUT =              10
CLIENT_INTERFACES =         "../conman/interfaces.client"
SERVER_INTERFACES =         "../conman/interfaces.server"
DNSMASQFILE =               "../conman/dnsmasq.conf"
HOSTAPDFILE =               "../conman/hostapd"
HOSTAPD_CONF_FILE =         "../conman/hostapd.conf"
WPA_PROTO_FILE =            "../conman/wpa_supplicant.conf.proto"
GET_SSID_TIMEOUT =          300   # Time given for someone to input WiFi credentials in server mode
RECONNECT_INTERVAL =        120   # Time to wait before trying to connect again

class Conman():
    def __init__(self):
        self.missedPing = 0
        self.connecting = True
        self.monitorByPing = True  # If false, call setConnected() to set whether connected or not
        self.firstAfterReboot = True  # So that we only ask for WiFi credentials on reboot

    def start(self, logFile="/var/log/conman.log", logLevel=logging.INFO, monitorInterval=600):
        logging.basicConfig(filename=logFile,level=logLevel,format='%(asctime)s %(levelname)s: %(message)s')
        logging.info("%s started by call to start", ModuleName)
        self.monitorByPing = False
        self.monitorInterval = monitorInterval
        reactor.callInThread(self.doConnect)
        # If reactor is running, we're part of another program
        if not reactor.running:
            signal.signal(signal.SIGINT, self.signalHandler)  # For catching SIGINT
            signal.signal(signal.SIGTERM, self.signalHandler)  # For catching SIGTERM
            reactor.run()

    def signalHandler(self, signal, frame):
        logging.debug("%s signalHandler received signal", ModuleName)
        reactor.stop()

    def listInterfaces(self):
        interfaces = []
        try:
            s = check_output(["sudo", "/usr/bin/sg_raw", "/dev/sr0", "11", "06", "20", "00", "00", "00", "00", "00", "01", "00"])
            logging.debug("%s startModem, sg_raw output: %s", ModuleName, s)
        except Exception as ex:
            logging.info("%s startModem sg_raw output: %s %s", ModuleName, type(ex), str(ex.args))
        try:
            time.sleep(8)
            ifconfig = check_output(["ifconfig"]).split()
            for interface in ("eth0", "wlan0", "eth1", "wwan0"):
                if interface in ifconfig:
                    interfaces.append(interface)
        except Exception as ex:
            logging.warning("%s Could not list interfaces", ModuleName)
            logging.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
        return interfaces
    
    def checkIfconfig(self, interface):
        connection = ""
        addr = ""
        try:
            ifconfig = check_output(["ifconfig", interface]).split()
            if ifconfig[5] == "inet":
                addr = ifconfig[6][5:]
                connection = interface
        except Exception as ex:
            logging.warning("%s Problem in checkIfconfig %s", ModuleName, interface)
            logging.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
        logging.info("%s Interface: %s, connections: %s, addr: %s", ModuleName, interface, connection, addr)
        return connection, addr
    
    def checkPing(self):
        attempt = 0
        cmd = 'ping continuumbridge.com'
        while attempt < 2: 
            try:
                p = pexpect.spawn(cmd)
            except:
                logging.error("%s Cannot spawn ping", ModuleName)
                attempt += 1
            index = p.expect(['time', pexpect.TIMEOUT, pexpect.EOF], timeout=PING_TIMEOUT)
            if index == 1 or index == 2:
                logging.warning("%s %s did not succeed", ModuleName, cmd)
                p.sendcontrol("c")
                cmd = 'ping bbc.co.uk'
                attempt += 1
            else:
                p.sendcontrol("c")
                return True
        # If we don't return before getting here, we've failed
        return False
     
    def startSakisThread(self):
        # Called in a thread
        logging.debug("%s startSakis", ModuleName)
        addr = ""
        usbAddr = ""
        lsusb = check_output(["lsusb"]).split()
        logging.debug("%s startSakis, lsusb: %s", ModuleName, str(lsusb))
        for l in lsusb:
            if l[:4] == "12d1":
                usbAddr = l[5:]
                break
        if usbAddr != "":
            sakis3gConf = "/etc/sakis3g.conf"
            i = open(sakis3gConf, 'r')
            o = open("sakis3g.tmp", 'w') 
            found = False
            replaced = False
            for line in i:
                logging.debug("%s startSakis. line in:  %s", ModuleName, line)
                if "USBMODEM" in line:
                    line = "USBMODEM=\"12d1:" + usbAddr + "\"\n"
                    logging.debug("%s startSakis. Modem: %s", ModuleName, line)
                o.write(line)
            i.close()
            o.close()
            call(["mv", "sakis3g.tmp", sakis3gConf])
        # Try to connect 6 times, each time increasing the waiting time
        for attempt in range (5):
            try:
                # sakis3g requires --sudo despite being run by root. Config from /etc/sakis3g.conf
                #s = check_output(["/usr/bin/sakis3g", "--sudo", "reconnect", "--debug"])
                s = check_output(["/usr/bin/sakis3g", "--sudo", "reconnect"])
                logging.debug("%s startSakis, attempt %s. s: %s", ModuleName, str(attempt), s)
                if "connected" in s.lower() or "reconnected" in s.lower():
                    logging.info("%s startSakis succeeded", ModuleName)
                    break
            except Exception as ex:
                logging.warning("%s startSakis sakis3g failed, attempt %s", ModuleName, str(attempt))
                logging.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
                time.sleep(attempt*60)
        connection, addr = self.checkIfconfig("ppp0")
        reactor.callFromThread(self.checkConnected, connection)
    
    def startSakis(self):
        reactor.callInThread(self.startSakisThread)

    def getCredentials(self):
        exe = "../conman/wificonfig.py "
        htmlfile = "../conman/ssidform.html"
        cmd = exe + htmlfile
        logging.debug("%s getCredentials exe = %s, htmlfile = %s", ModuleName, exe, htmlfile)
        try:
            p = pexpect.spawn(cmd)
        except Exception as ex:
            logging.warning("%s Cannot run wificonfig.py", ModuleName)
            logging.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
            return
        index = p.expect(['Credentials.*', pexpect.TIMEOUT, pexpect.EOF], timeout=GET_SSID_TIMEOUT)
        if index == 1:
            logging.warning("%s SSID and WPA key not supplied before timeout", ModuleName)
            return False, "none", "none"
        elif index == 2:
            logging.warning("%s EOF when asking for SSID & WPA key", ModuleName)
            return False, "none", "none"
        else:
            raw = p.after.split()
            logging.debug("%s Credentials = %s", ModuleName, raw)
            if len(raw) < 3:
                logging.warning("%s Badly formed SSID & WPA key: %s", ModuleName, raw)
                return False, "none", "none"
            ssid = raw[2]
            wpa_key = raw[3]
            if len(raw) > 4:
                for i in range(4, len(raw)):
                    wpa_key += " " + raw[i]
            logging.info("%s SSID = %s, WPA = %s", ModuleName, ssid, wpa_key)
            return True, ssid, wpa_key
        p.sendcontrol("c")
    
    def switchwlan0(self, switchTo):
        logging.info("%s Switching to %s", ModuleName, switchTo)
        if switchTo == "server":
            call(["ifdown", "wlan0"])
            logging.debug("%s wlan0 down", ModuleName)
            call(["killall", "wpa_supplicant"])
            logging.debug("%s wpa_supplicant process killed", ModuleName)
            # In case dnsmasq and hostapd already running;
            call(["service", "dnsmasq", "stop"])
            logging.info("%s dnsmasq stopped", ModuleName)
            call(["service", "hostapd", " stop"])
            logging.info("%s hostapd stopped", ModuleName)
            call(["cp", SERVER_INTERFACES, "/etc/network/interfaces"])
            call(["ifup", "wlan0"])
            logging.debug("%s wlan0 up", ModuleName)
    
            # dnsmasq - dhcp server
            call(["cp", DNSMASQFILE, "/etc/dnsmasq.conf"])
            call(["service", "dnsmasq", "start"])
            logging.info("%s dnsmasq started", ModuleName)
            
            # hostapd configuration and start
            call(["cp", HOSTAPDFILE, "/etc/default/hostapd"])
            # Just in case it's not there:
            call(["cp", HOSTAPD_CONF_FILE, "/etc/hostapd/hostapd.conf"])
            call(["service",  "hostapd", "start"])
            logging.info("%s hostapd started", ModuleName)
            # Because wlan0 loses its ip address when hostapd is started
            call(["ifconfig", "wlan0", "10.0.0.1"])
            logging.info("%s Wifi in server mode", ModuleName)
        elif switchTo == "client":
            call(["ifdown", "wlan0"])
            logging.debug("%s wlan0 down", ModuleName)
            call(["service", "dnsmasq", "stop"])
            logging.info("%s dnsmasq stopped", ModuleName)
            call(["service", "hostapd", " stop"])
            logging.info("%s hostapd stopped", ModuleName)
            try:
                call(["rm", "/etc/dnsmasq.conf"])
            except:
                logging.info("%s dUnable to remove /etc/dnsmasq.conf. Already in client mode?", ModuleName)
            try:
                call(["rm", "/etc/default/hostapd"])
            except:
                logging.info("%s Unable to remove /etc/default.hostapd. Already in client mode?", ModuleName)
            call(["cp", CLIENT_INTERFACES, "/etc/network/interfaces"])
            time.sleep(1)
            connected = self.connectWlan0()
            logging.info("%s Wifi in client mode, connected: %s", ModuleName, connected)
            return connected
        else:
            logging.debug("%s switch. Must switch to either client or server", ModuleName)
    
    def connectWlan0(self):
        connected = False
        try:
            p = pexpect.spawn("ifup wlan0")
        except:
            logging.warning("%s Cannot spawn ifup wlan0", ModuleName)
        else:
            index = p.expect(['bound',  pexpect.TIMEOUT, pexpect.EOF], timeout=120)
            if index == 0:
                logging.info("%s connectWlan0. wlan0 connected in client mode", ModuleName)
                connected = True
            elif index == 2:
                for t in p.before.split():
                    if t == "already":
                        logging.info("%s connectWlan0. wlan0 already connected. No need to connect.", ModuleName)
                        connected = True
                        break
                if not connected:
                    logging.info("%s connectWlan0. Timeout without being already connected", ModuleName)
            else:
                logging.warning("%s connectWlan0. DHCP timed out", ModuleName)
                p.sendcontrol("c")
        return connected
    
    def wifiConnect(self):
        """ If the Bridge is not connected assume that we are going to connect
            using WiFi. Try to connect using current settings. If we cannot,
            switch to server mode and ask user for SSDI and WPA key with a 
            2 minute timeout. If we have got credentials, use these and try
            again, otherwise return with failed status.
        """
        logging.info("%s wifiConnect. Switching to server mode", ModuleName)
        self.switchwlan0("server")
        # Allow time for server to start
        time.sleep(3)
        gotCreds, ssid, wpa_key = self.getCredentials()
        if gotCreds:
            wpa_config_file = "/etc/wpa_supplicant/wpa_supplicant.conf"
            wpa_tmp_file = "/etc/wpa_supplicant/wpa_supplicant.conf.tmp"
            # If SSID already in wpa_supplicant.conf, just change the WPA key
            i = open(wpa_config_file, 'r')
            o = open(wpa_tmp_file, 'w') 
            found = False
            replaced = False
            for line in i:
                #logging.debug("%s wifiConnect. line in:  %s", ModuleName, line)
                if "ssid" in line or "SSID" in line:
                    l1 = [l.strip(' ') for l in line]
                    if l1[0] != "#":
                        if ssid in line:
                            found = True
                            #logging.debug("%s wifiConnect. found:  %s", ModuleName, line)
                elif found:
                    if "psk=" in line or "psk =" in line:
                        line = "   psk=\"" + wpa_key +"\"\n"
                        #logging.debug("%s wifiConnect. found, line out:  %s", ModuleName, line)
                        found = False
                        replaced = True
                #logging.debug("%s wifiConnect. line out:  %s", ModuleName, line)
                o.write(line)
            i.close()
            o.close()
            logging.debug("%s wifiConnect. replaced:  %s", ModuleName, replaced)
            if replaced:
                call(["mv", wpa_tmp_file, wpa_config_file])
                logging.debug("%s wifiConnect. mv wpa_tmp file wpa_config_file", ModuleName)
            else:
                # If SSID is not found, add a new network to the list
                i = open(WPA_PROTO_FILE, 'r')
                o = open(wpa_config_file, 'a')  #append new SSID to file
                for line in i:
                    line = line.replace("XXXX", ssid)
                    line = line.replace("YYYY", wpa_key)
                    o.write(line) 
            i.close()
            o.close()
        else:
            logging.info("%s Did not get WiFi SSID and WPA from a human", ModuleName)
        self.switchwlan0("client")
        time.sleep(10)
        return "wlan0"
    
    def doConnect(self):
        self.connecting = True
        interfaces = self.listInterfaces()
        logging.info("%s Available interfaces: %s", ModuleName, interfaces)
        addr = ""
        if "eth0" in interfaces:
            connection, addr = self.checkIfconfig("eth0")
        if addr == "" and "wlan0" in interfaces:
            connection, addr = self.checkIfconfig("wlan0")
            # Indicates wlan0 had the server ip address
            if addr == "10.0.0.1":
                self.switchwlan0("client")
                connection, addr = self.checkIfconfig("wlan0")
            else:
                connection, addr = self.checkIfconfig("wlan0")
        if addr == "" and "eth1" in interfaces:
            try:
                s = check_output(["dhclient", "eth1"])
            except Exception as ex:
                logging.warning("%s Problem in dhclient eth1", ModuleName)
                logging.warning("%s Exception: %s %s", ModuleName, type(ex), str(ex.args))
            connection, addr = self.checkIfconfig("eth1")
        logging.debug("%s doConnect, addr: %s, interfaces: %s", ModuleName, addr, interfaces)
        if addr == "" and "wwan0" in interfaces:
            connection, addr = self.checkIfconfig("ppp0")
            if addr == "":
                logging.debug("%s doConnect, calling startSakis", ModuleName)
                reactor.callFromThread(self.startSakis)
        else:
            reactor.callFromThread(self.checkConnected, connection)
    
    def startDoConnect(self):
        reactor.callInThread(self.doConnect)

    def checkConnected(self, connection):
        logging.info("%s checkConnected. Connected by: %s", ModuleName, connection)
        if connection == "":
            interfaces = self.listInterfaces()
            if "wlan0" in interfaces:
                if self.firstAfterReboot:
                    logging.debug("%s checkConnected. Calling wifiConnect", ModuleName)
                    d1 = threads.deferToThread(self.wifiConnect)
                    d1.addCallback(self.monitor)
                else:
                    self.switchwlan0("client")
                    reactor.callLater(RECONNECT_INTERVAL, self.startDoConnect)
            else:
                reactor.callLater(RECONNECT_INTERVAL, self.startDoConnect)
        else:
            self.connecting = False
            self.monitor(connection)
    
    def setConnected(self, connected):
        if not connected and not self.connecting:
            reactor.callInThread(self.doConnect)

    def monitor(self, connection):
        self.firstAfterReboot = False
        if self.monitorByPing:
            d = threads.deferToThread(self.checkPing)
            d.addCallback(self.checkMonitor)

    def checkMonitor(self, connected):
        logging.debug("%s checkMonitor. connected: %s", ModuleName, connected)
        if not connected:
            if self.missedPing > 0:
                logging.debug("%s checkMonitor. Calling doConnect", ModuleName)
                self.missedPing = 0
                reactor.callInThread(self.doConnect)
            else:
                logging.debug("%s checkMonitor. Missed ping", ModuleName)
                self.missedPing += 1
                reactor.callLater(self.monitorInterval/2, self.monitor, "")
        else:
            self.missedPing = 0
            reactor.callLater(self.monitorInterval, self.monitor, "")

if __name__ == '__main__':
    c = Conman()
    c.start(logFile="/var/log/conman.log", logLevel=logging.DEBUG, monitorInterval=600)
