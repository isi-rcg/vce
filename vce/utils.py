"""Utility classes."""

from itertools import chain
from io import TextIOWrapper
import logging
import netifaces
import os
from pathlib import Path
import socket
import sys
from strictyaml import load, Str, Int, Float, Datetime, \
    Optional, Map, Seq, EmptyList
from influxdb import InfluxDBClient


logger = logging.getLogger(__name__)
log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']


def log_enabled(level):
    """Check if logging is enabled at the given level."""

    return logging.getLogger().isEnabledFor(getattr(logging, level.upper()))


def set_logger(level='WARNING', out=sys.stderr):
    """Set the log level and output."""

    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.basicConfig(level=getattr(logging, level.upper()),
                        stream=out,
                        format=('[%(asctime)s] '
                                '(%(module)s.%(funcName)s#%(lineno)s) '
                                '%(levelname)s: %(message)s'))


#: StrictYAML schema of the constellation configuration
schema = Map({
    'system': Map({
        'awscli': Str(),
        'stackname': Str(),
        'zone': Str(),
        'keyname': Str(),
        Optional('ip_range', default=''): Str(),
        'server': Map({
            'hostname': Str(),
            Optional('ip', default=''): Str(),
            'type': Str(),
            'ami': Str(),
            'snap': Str(),
            'user': Str()
        }),
        'db': Map({
            'name': Str(),
            'host': Str(),
            'port': Int()
        }),
        'orbits': Map({
            'start': Datetime(),
            'step': Float(),
            'duration': Float()
        }),
        'agent_interval': Float(),
        'metrics_interval': Float(),
        'start_delay': Int()
    }),
    'satellites': Seq(Map({
        'hostname': Str(),
        Optional('ip', default=''): Str(),
        'type': Str(),
        'ami': Str(),
        'snap': Str(),
        'user': Str(),
        'cmd': Str(),
        'tle1': Str(),
        'tle2': Str(),
        Optional('links'): Seq(Str()) | EmptyList(),
        Optional('midar'): Map({'state': Str()})
    })),
    'stations': Seq(Map({
        'hostname': Str(),
        Optional('ip', default=''): Str(),
        'type': Str(),
        'ami': Str(),
        'snap': Str(),
        'user': Str(),
        'cmd': Str(),
        'lat': Float(),
        'lon': Float(),
        'alt': Float(),
        Optional('links'): Seq(Str()) | EmptyList()
    }))
})


def assign_ip_addr(config):
    """Extend the constellation config with the ip address of each node
    (server, satellite, base station)."""

    server = config['system']['server']
    satellites = config['satellites']
    stations = config['stations']

    addr = 0
    for node in chain([server], satellites, stations):
        addr += 3 if addr % 256 == 254 else 1
        if addr > 255*254:
            raise ValueError('Only up to 255*254 hosts are supported')
        node['ip'] = f'10.0.{1+addr//256}.{addr%256}'

    config['system']['ip_range'] = '10.0.0.0/16'
    return config


def parse(yaml, get_data=True):
    """Parse the input YAML configuration of the constellation."""

    if isinstance(yaml, TextIOWrapper):
        # read input file
        yaml = yaml.read()

    config = load(yaml, schema)
    assign_ip_addr(config)

    return config.data if get_data else config


#: Cached map of hostname aliases
alias = None


def host_alias(hostname):
    """Find the last hostname alias in the file specified by the
    environment variable HOSTALIASES."""
    global alias

    if alias is None:
        alias = {}
        if 'HOSTALIASES' in os.environ:
            alias_file = Path(os.environ['HOSTALIASES'])
            if alias_file.is_file():
                with open(alias_file) as f:
                    for line in f:
                        words = line.partition('#')[0].split()
                        if len(words) == 2:
                            alias[words[0]] = words[1]

    return alias.get(hostname, hostname)


def get_iface(addr):
    """Find the interface where a given source ip is used."""

    for iface in netifaces.interfaces():
        addresses = netifaces.ifaddresses(iface)
        for netconfig in addresses.get(netifaces.AF_INET, []):
            if netconfig['addr'] == addr:
                return iface

    return None


def get_addr(hostname):
    """Find ip address of given hostname."""
    try:
        return socket.gethostbyname(host_alias(hostname))
    except socket.gaierror:
        return None


def db_client(config, use_db=True):
    """Get an InfluxDB client for the timeseries database."""

    host = host_alias(config['system']['db']['host'])
    port = config['system']['db']['port']
    name = config['system']['db']['name'] if use_db else None

    try:
        client = InfluxDBClient(host=host, port=port, database=name)
        version = client.ping()
        logger.info(f'Connected to InfluxDB version {version} ({host}:{port})')
        return client

    except Exception as e:
        logger.error(f'Error connecting to ({host}:{port}): {e}')
        sys.exit(1)
