
# tcpTransfer
A transfer module from UR to PI

# deployment
1.  place all files/folders under src to /usr/local/lib/python2.7/dist-packages directory
2.  place all files under cfg/etc to /etc directory
3.  restart PI and here we go

# other configuration for PI OS
To disable dhcp and use a static IP for eth0, please do as followings:
1.  disable dhcpd.service
    sudo systemctl disable dhcpcd.service
    sudo systemctl enable networking.service
2.  update /etc/network/interfaces as the one in the root of this repo
3.  reboot

Methods to find out gatway:
  route -n
  or 
  netstate -r -n

Change the keyboard layout
1. sudo raspi-config
2. sudo dpkg-reconfigure keyboard-configuration 
for me I choose Dell 101 Keybaord

To make twistd can listen on 80
>sudo setcap CAP_NET_BIND_SERVICE+ep /usr/bin/twistd

>sudo setcap CAP_NET_BIND_SERIVCE+ep /usr/local/bin/twistd

