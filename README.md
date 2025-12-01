# Hoster

A simple "etc/hosts" file injection tool to resolve names of local Docker containers on the host.

Hoster can be run as a Docker container or as a systemd unit.

## Docker container

To run as a docker container simply build a docker image with a provided Dockerfile

```shell
docker build -t hoster:latst .
```

And run the container

```shell
docker run -d \
    -v /var/run/docker.sock:/tmp/docker.sock \
    -v /etc/hosts:/tmp/hosts \
    hoster:latst
```
The `docker.sock` is mounted to allow hoster to listen for Docker events and automatically register containers IP.

Hoster inserts into the host's `/etc/hosts` file an entry per running container and keeps the file updated with any started/stoped container.

## Systemd unit

NOTE: Make sure you have installed python3 and `docker` lib.

Copy script to somewhere, for instance `/usr/local/bin` and make it executable as well as change ownerships.

```shell
cp hoster.py /usr/local/bin/
sudo chown root:root /usr/local/bin/hoster.py
sudo chmod +x /usr/local/bin/hoster.py
```

Copy systemd service file and active it:
```shell
cp docker-update-hosts.service /etc/systemd/system/docker-update-hosts.service
sudo chow root:root /etc/systemd/system/docker-update-hosts.service
sudo systemctl enable --now docker-update-hosts.service
```

Hoster will directly work with your `/etc/hosts` file using docker socket.

## Container Registration

Hoster provides by default the entries `<container name>, <hostname>, <container id>` for each container and the aliases for each network. Containers are automatically registered when they start, and removed when they die.

For example, the following container would be available via DNS as `myname`, `myhostname`, `et54rfgt567` and `myserver.com`:

```shell
docker run -d \
    --name myname \
    --hostname myhostname \
    --network somenetwork --network-alias "myserver.com" \
    mycontainer
```

If you need more features like **systemd interation** and **dns forwarding** please check [resolvable](https://hub.docker.com/r/mgood/resolvable/)

Any contribution is, of course, welcome. :)
