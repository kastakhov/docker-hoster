#!/usr/bin/env python3
import docker
import argparse
import shutil
import signal
import time
import sys
import os
import json
import logging

enclosing_pattern = "#-----------Docker-Hoster-Domains-----------"
hosts_footer = "#-----------Do-not-add-hosts-after-this-line-----------"

hosts_path = "/tmp/hosts"
hosts = {}

start_actions = ["start"]
stop_actions = ["stop","die","destroy","kill"]
rename_actions = ["rename"]

logging.basicConfig(
  level=logging.INFO,
  format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def signal_handler(signal, frame):
  global hosts
  logger.info("Received signal to exit, cleaning up...")
  hosts = {}
  update_hosts_file()
  sys.exit(0)

def main():
  # register the exit signals
  signal.signal(signal.SIGINT, signal_handler)
  signal.signal(signal.SIGTERM, signal_handler)

  args = parse_args()
  global hosts_path
  hosts_path = args.file

  try:
    dockerClient = docker.APIClient(base_url='unix://%s' % args.socket)
    logger.info(f"Connected to docker socket at {args.socket}")
  except Exception as e:
    logger.error(f"Failed to connect to docker socket at {args.socket}: {e}")
    sys.exit(1)

  #get running containers
  for c in dockerClient.containers(quiet=True, all=False):
    container_id = c["Id"]
    hosts[container_id] = get_container_data(dockerClient, container_id)

  update_hosts_file()

  #listen for events to keep the hosts file updated
  events = dockerClient.events(decode=True)
  for e in events:
    logger.debug(f"Event received: {json.dumps(e)}")
    if e["Type"] != "container":
      continue

    action = e.get("Action")
    container_id = e.get("Actor", {}).get("ID")

    if not container_id or not action:
      logger.warning(f"Could not parse container ID or action from event: {json.dumps(e)}")
      continue

    if action in start_actions:
      logger.info(f"Container started, adding/updating hosts entry for container ID {container_id}")
      hosts[container_id] = get_container_data(dockerClient, container_id)
      update_hosts_file()

    if action in stop_actions:
      if container_id in hosts:
        logger.info(f"Container stopped/removed, removing hosts entry for container ID {container_id}")
        hosts.pop(container_id)
        update_hosts_file()

    if action in rename_actions:
      if container_id in hosts:
        logger.info(f"Container renamed, updating hosts entry for container ID {container_id}")
        hosts[container_id] = get_container_data(dockerClient, container_id)
        update_hosts_file()


def get_container_data(dockerClient, container_id):
  result = []
  #extract all the info with the docker api
  info = dockerClient.inspect_container(container_id)
  logger.debug(f"Container info: {json.dumps(info)}")

  container_name = info["Name"].strip("/")
  container_hostname = info["Config"].get("Hostname")
  container_domainname = info["Config"].get("Domainname")

  if container_domainname:
    container_hostname = container_hostname + "." + container_domainname

  domains = [container_name, container_hostname]

  for values in info["NetworkSettings"]["Networks"].values():
    if values.get("Aliases"):
      domains.extend(values["Aliases"])

    result.append(
      {
        "ip": values["IPAddress"],
        "name": container_name,
        "domains": set(domains)
      }
    )

  return result


def update_hosts_file():
  lines_to_add = []
  if not hosts:
    logger.info("No docker containers are found, clearing hosts file entries.")
  else:
    logger.info("Rewriting hosts file with:")
    for host in hosts.values():
      for network in host:
        logger.info(" * container name: '%s', ip: '%s', domains: %s" % (network["name"], network["ip"], network["domains"]))
        lines_to_add.append("%s\t%s # %s\n"%(network["ip"]," ".join(network["domains"]), network["name"]))

  #read all the lines of thge original file
  lines = []
  with open(hosts_path,"r+") as hosts_file:
    lines = hosts_file.readlines()

  #remove all the lines after the known pattern
  for i, line in enumerate(lines):
    if line == enclosing_pattern:
      lines = lines[:i]
      break

  #remove all the trailing newlines on the line list
  if lines:
    while lines[-1].strip() == "": lines.pop()

  #append all the domain lines
  if hosts:
    lines.append("\n\n" + enclosing_pattern)

    for line in lines_to_add:
      lines.append(line)

    lines.append(hosts_footer + "\n")

  #write it on the auxiliar file
  aux_file_path = hosts_path+".aux"
  with open(aux_file_path,"w") as aux_hosts:
    aux_hosts.writelines(lines)

  #replace etc/hosts with aux file, making it atomic
  shutil.move(aux_file_path, hosts_path)


def parse_args():
  parser = argparse.ArgumentParser(description='Synchronize running docker container IPs with host /etc/hosts file.')
  parser.add_argument('socket', type=str, nargs="?", default="tmp/docker.sock", help='The docker socket to listen for docker events.')
  parser.add_argument('file', type=str, nargs="?", default="/tmp/hosts", help='The /etc/hosts file to sync the containers with.')
  return parser.parse_args()


if __name__ == '__main__':
  main()
