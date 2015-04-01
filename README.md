# Conman
Conman is a connection manager for a Raspberry Pi. It has been tested with Raspberry Pi model a (B and B+) and model 2 (B), all running the Raspbian operating system. There is little that is specific to either hardward or Linux distribution and it is likely to function in other environments with little or no modification. Conman was written for the ContinuumBridge cbridge platform, but it has been tested as a stand-alone application.

Depending on which interfaces are available, conman will try to connect on the following, in priority order:

* Ethernet (eht0)
* WiFi (wlan0)
* 3G USB dongle (eth1 or wwan0, depending on dongle type)
 

