# rpi-phone
an old phone used to store audio messages

create service :
sudo nano /etc/systemd/system/phone.service

activate service :
sudo systemctl daemon-reload
sudo systemctl enable phone.service

start service :
sudo systemctl start phone.service

logs :
journalctl -u phone.service -f

reglage volume :
amixer set Headphone 50%
amixer set Lineout 50%
amixer set DAC 64