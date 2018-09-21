xhost +local:`sudo docker inspect --format='{{ .Config.Hostname }}' pidrone`
sudo docker start pidrone
sudo docker attach pidrone
