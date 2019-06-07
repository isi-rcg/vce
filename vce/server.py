"""VCE server (running on a dedicated VM)."""

import logging
import responder
import click
from datetime import datetime, timedelta
from itertools import chain
from .orbits import get_delays
from .utils import parse, db_client


logger = logging.getLogger(__name__)
api = responder.API()
db, hosts, sim_start, orbits_start, orbits_end = [None]*5


@click.group()
def server():
    """VCE control server (started on a dedicated AWS VM)."""
    pass


@server.command()
@click.argument('config', type=click.File('r'))
def run(config):
    """Run the VCE control server.

    This command starts an HTTP server providing constellation
    parameters from a timeseries database.
    """
    config = parse(config)

    # setup read-only global variables for API requests
    global db, hosts, sim_start, orbits_start, orbits_end
    db = db_client(config)
    hosts = [node['hostname'] for node in
             chain(config['satellites'], config['stations'])]
    sim_start = datetime.now()
    orbits_start = config['system']['orbits']['start']
    orbits_end = (orbits_start +
                  timedelta(minutes=config['system']['orbits']['duration']))

    # start listening to incoming requests
    api.run(address='0.0.0.0', port=8888, debug=True, log_level=logger.level)


@api.route('/net/src/{src}')
def respond(req, resp, *, src):
    """Respond to HTTP requests with network parameters for a source."""
    if src not in hosts:
        resp.status_code = 404
        return

    # stop orbit propagation after orbits_end
    t = orbits_start + (datetime.now() - sim_start)
    t = min(t, orbits_end)

    params = {}
    for dst, delay in get_delays(db, t, src).items():
        if delay is None:
            # drop all packets if unreachable
            params[dst] = {'loss': 100}
        elif delay > 0:
            # set delay for reachable destinations
            params[dst] = {'delay': delay*1000}

    resp.media = params
