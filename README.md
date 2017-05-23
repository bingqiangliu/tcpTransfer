# tcpTransfer
A transfer module from UR to PI

To disable dhcp and use a static IP for eth0, please do as followings:
1.  disable dhcpd.service
    sudo systemctl stop dhcpcd.service
2.  update /etc/network/interfaces as the one in the root of this repo
3.  reboot

Methods to find out gatway:
route -n
or 
netstate -r -n
