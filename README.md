# Conman

Introduction
------------
Conman is a connection manager for a Raspberry Pi. It has been tested with Raspberry Pi model a (B and B+) and model 2 (B), all running the Raspbian operating system. There is little that is specific to either hardward or Linux distribution and it is likely to function in other environments with little or no modification. Conman was written for the ContinuumBridge cbridge platform (http://continuumbridge.readme.io/v1.0/docs/overview), but it has been tested as a stand-alone application.

Depending on which interfaces are available, conman will try to connect on the following, in priority order:

* Ethernet (eht0)
* WiFi (wlan0)
* 3G USB dongle (eth1 or wwan0, depending on dongle type)
 
If you want to use a 3G USB dongle, the steps for determining what type of dongle you have and configuring the network parameters is described here: http://continuumbridge.readme.io/v1.0/docs/hardware. There is a small difference: the sakis3g template file referred to can be found in this GitHub repository. 

A very useful function of conman is that if it can't connect on any interface and it detects that the Raspberry Pi has a Wifi USB dongle, it will switch it into access point mode so that you can enter a WiFi access point SSID and APN key. This is described under the "operation" section, below.

Installation
------------
Clone this repository, by typing:

    git clone https://github.com/ContinuumBridge/conman.git

Then type: 

    sudo conman/setup
    sudo reboot

Conman will be started automatically. That's all you need to do, so unless you want to turn conman off and on (which is likely to be during development), skip the rest of this section and go onto the Operation section.

If you don't want conman to start automatically on boot, type:

    sudo update-rc.d -f conman remove

To make conman start automatically again, type:

     sudo update-rc.d conman defaults
 
If conman is not set to start automratically, you can start, stop and restart it using:
 
     sudo service conman start
     sudo service conman stop
     sudo service conman restart
 
Non-automatic mode is principally of use during development or debug.

Operation
---------
Conman works as follows. On boot:
 
 * It will connect using an Ethernet interface, if present.
 * If Ethernet is not present, it will try to connect using WiFi, if it has details for a local access point.
 * If there is no WiFi dongle, or there is no known local access point it will then try to use a 3G dongle, if present.
 * If it can't connect on anything and there is a WiFi dongle, it will switch this into access point mode.
 * Bear in mind that there will be a delay of a minute or two before the Raspberry Pi goes into access point mode.
 
When in access point mode, you can use a PC, tablet or phone to connect to the access point (it will be listed as ContinuumBridge). When you have done this, open a browser and type: 10.0.0.1. You should see a page like this:

![conman ssid page](https://github.com/ContinuumBridge/conman/blob/master/conman_ssid.jpg)

Enter the SSID and WPA key for your access point and then press Submit. You should see this page:

![conman thanks page](https://github.com/ContinuumBridge/conman/blob/master/conman_thanks.jpg)

Conman then uses the credentials you have just given it and reconfigure back into a client and connect to the access point. It actually writes the credentials to the file /etc/wpa_supplicant/wpa_supplicant.conf. You can edit this file manually, for example if you know the credentials of a new access point while you are still connected to the Raspberry Pi, or you want to remove an access point from its list. 

Every 12 minutes, conman tries to ping a couple of servers. If it can't see either of them, it tries again after another six minutes and then repeats the process that it does on boot, with the exception that it only ever goes into server mode immediately after booting. One use of this feature is automatic fallback from Ethernet or WiFi to 3G/cellular. If this happens, the Raspberry Pi will remain connected to the cellular interface until something causes it to search again, such a a reboot, manual intervention or the cellular connection going down (which actually happens quite often in normal operation, possibly because many network operators drop a connection to a device that has been conencted for some time).

Code
----
Conman is written entirely in Python and the code is all contained in the files conman.py and wificonfig.py. If you look in conman.py, you'll see there is a lot of editing of template files, copying files around and starting and stopping of various services, especially to put the Raspberry Pi into access point mode. All this may look strange, but has been found to be robust over a long period of time and with dozens of Raspberry Pies running the software. 

Some use of Python Twisted (https://twistedmatrix.com/trac/) is made, to allow event-driven programming in conman.py and to provide a very simple "web server" in wifconfig.py. If anyone wants to modify any of these parts of the code and isn't familiar with Twisted, we suggest you look here: http://continuumbridge.readme.io/v1.0/docs/developing-bridge-apps-1.

Acknowledgement
---------------
Conman has been made open source as a result of a competition run by the London Raspberry Pint Meetup Group (http://www.meetup.com/Raspberry-Pint-London/). 
![conman thanks page](https://github.com/ContinuumBridge/conman/blob/master/Raspberry_Pint.jpg)

Numerous sources on the web were consulted during the development of conman (a process that started in late 2013). The ones that we used most are listed below. Our thanks to all the authors.

* [hostapd: Ubuntu server as a wireless access point](http://www.danbishop.org/2011/12/11/using-hostapd-to-add-wireless-access-point-capabilities-to-an-ubuntu-server/)
* A predecessor of: [The Pi-Point Raspberry Pi Wireless Access Point](http://www.pi-point.co.uk/), which I have just found when I came to write this.
* [Raspberry Pi - Installing the Edimax EW-7811Un USB WiFi Adapter](http://www.savagehomeautomation.com/projects/raspberry-pi-installing-the-edimax-ew-7811un-usb-wifi-adapte.html#.UOdb5XYgik0)
* [Huawei E3131 on Wheezy](http://www.raspberrypi.org/forums/viewtopic.php?t=18996)
* [Testing & Setting the USB current limiter on the Raspberry Pi B+](https://projects.drogon.net/testing-setting-the-usb-current-limiter-on-the-raspberry-pi-b/)
