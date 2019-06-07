import os
import click
from . import db
from . import orbits
from . import cloud
from . import server
from . import agent
from .utils import set_logger


@click.group()
def cli():
    set_logger(os.environ.get('LOGLEVEL', 'WARNING').upper())
    pass


def main():
    cli.add_command(db.db)
    cli.add_command(orbits.orbits)
    cli.add_command(cloud.cloud)
    cli.add_command(server.server)
    cli.add_command(agent.agent)
    cli(prog_name='vce')


if __name__ == '__main__':
    main()
