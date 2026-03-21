# Rpi-phone  
an old phone used to store audio messages  

## Service  
create service :  
sudo nano /etc/systemd/system/phone.service  
sudo nano /etc/systemd/system/hotspot.service  

activate service :
sudo systemctl daemon-reload  
sudo systemctl enable phone.service  

start service :
sudo systemctl start phone.service  

## Logs :  
journalctl -u phone.service -f  

## Volume management :  
amixer set Headphone 50%  
amixer set Lineout 50%  
amixer set DAC 64  

## Hotspot  
nmcli device wifi hotspot ifname wlan0 ssid PiPhone password raspberry  

## Local  
activate gadget mode to join rpi on usb  
ip : 192.168.7.2  
ssh alex@192.168.7.2  
adress for message management : 10.42.0.1  

