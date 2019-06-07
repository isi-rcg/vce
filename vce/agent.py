"""VCE agent running on each node (satellite or base station)."""

import time
import logging
import platform
import subprocess
import click
import requests
import pprint
import sys
from .utils import log_enabled, parse, host_alias, get_addr, get_iface

logger = logging.getLogger(__name__)


@click.group()
def agent():
    """VCE agent (started on each constellation VM)."""
    pass


def apply_config(iface, src, dst, config):
    """Apply changes to network configuration."""

    command = ['tcset', iface, '--change',
               '--src-network', f'{src}',
               '--dst-network', f'{dst}']

    for key, value in config.items():
        value = str(float(value)).rstrip('0').rstrip('.')
        if key == 'delay':
            command.append('--delay')
            command.append(f'{value}ms')
        elif key == 'rate':
            command.append('--rate')
            command.append(f'{value}Kbps')
        elif key == 'loss':
            command.append('--loss')
            command.append(f'{value}%')
        elif key == 'corrupt':
            command.append('--corrupt')
            command.append(f'{value}')
        else:
            raise ValueError('Unknown parameter {key}')

    # apply parameters in a subprocess
    try:
        subprocess.run(command, capture_output=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f'Error invoking: {" ".join(e.cmd)}\n{e.stdout}')
    except FileNotFoundError as e:
        print(f'Command unknown: {e}')


def polling(src_host, server, period):
    """Poll the server with /net/src/host queries and
    apply network configurations using `tcconfig`.

    To run without root privileges:
    `sudo setcap cap_net_admin+ep /sbin/tc`
    """

    # ip address and network interface of this node
    src = get_addr(host_alias(src_host))
    if not src:
        raise ValueError(f'Cannot resolve hostname {src_host}')

    iface = get_iface(src)
    if not iface:
        raise ValueError(f'Cannot find interface of {src}')

    # server url to obtain outgoing network parameters
    url = f'http://{server}:8888/net/src/{src_host}'

    last_net_config = {}
    while True:
        try:
            r = requests.get(url)
            net_config = r.json()
            if log_enabled('INFO'):
                logger.info('Received configurations:\n' +
                            pprint.pformat(net_config, indent=2))

            # apply only when configuration changed
            if net_config != last_net_config:
                for dst_host, config in net_config.items():
                    dst = get_addr(host_alias(dst_host))
                    if not dst:
                        raise ValueError(f'Cannot resolve hostname {dst_host}')
                    apply_config(iface, src, dst, config)

                last_net_config = net_config

        except requests.exceptions.InvalidURL:
            print(f'Error: invalid URL {url}')
            sys.exit(1)
        except requests.exceptions.ConnectionError:
            print(f'Error: cannot connect to {server}:8888')

        time.sleep(period)


@agent.command()
@click.argument('config', type=click.File('r'))
@click.option('--host', default=platform.node(),
              help='Run as the given source host.')
def run(config, host):
    """Run the VCE agent.

    This command starts querying the VCE server for constellation
    parameters and applies them to the local virtual machine.
    """
    config = parse(config)

    # server hostname
    server = host_alias(config['system']['server']['hostname'])

    # inteval betwen requests to the server
    period = config['system']['agent_interval']

    # start the polling loop
    polling(host, server, period)
