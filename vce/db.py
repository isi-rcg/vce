import logging
import click
from .utils import parse, db_client


logger = logging.getLogger(__name__)


@click.group()
def db():
    """Timeseries database management"""
    pass


@db.command()
@click.argument('config', type=click.File('r'))
def reset(config):
    """Reset the timeseries database.

    This command connects to InfluxDB to create an empty database.
    """
    config = parse(config)
    client = db_client(config, False)
    name = config['system']['db']['name']
    for db in client.get_list_database():
        if db['name'] == name:
            print(f'Deleting database {name}...')
            client.query(f'DROP DATABASE {name}')
            logging.info(f'Deleted database {name}')
            break
    print(f'Creating database {name}...')
    client.query(f'CREATE DATABASE {name}')
    logging.info(f'Created database {name}')


def get_databases(client):
    """Get the names of all databases."""
    for db in client.get_list_database():
        if db['name'] != '_internal':
            yield db['name']


def get_measurements(client, db):
    """Get the names of measurement timeseries in a database."""
    rs = client.query(f'SHOW MEASUREMENTS ON {db}')
    for m in rs.get_points('measurements'):
        yield m['name']


def get_fields(client, db, measurement):
    """Get all field names for a measurement timeseries."""
    rs = client.query(f'SHOW FIELD KEYS ON {db} FROM {measurement}')
    for field in rs.get_points(measurement):
        yield field['fieldKey'], field['fieldType']


def get_field_count(client, measurement, field):
    """Get the number of data points for a field in a measument timeseries."""
    rs = client.query(f'SELECT COUNT({field}) FROM {measurement}')
    return next(rs.get_points(measurement))['count']


def get_tags(client, db, measurement):
    """Get all tag names for a measurement timeseries."""
    rs = client.query(f'SHOW TAG KEYS ON {db} FROM {measurement}')
    for tag in rs.get_points(measurement):
        yield tag['tagKey']


def get_tag_values(client, db, measurement, tag):
    """Get all tag values for a measurement tag."""
    query = f'SHOW TAG VALUES ON {db} FROM {measurement} WITH KEY = "{tag}"'
    rs = client.query(query)
    for value in rs.get_points(measurement):
        yield value['value']


@db.command()
@click.argument('config', type=click.File('r'))
def info(config):
    """Show summary information on the timeseries database.

    This command connects to InfluxDB and analyzes the list of
    measurements, tags, and fields present.
    """
    config = parse(config)
    client = db_client(config)
    for db in get_databases(client):
        print(f'== Database {db} ==')
        for measurement in get_measurements(client, db):
            print(f"> Measurement '{measurement}'")

            for field, datatype in get_fields(client, db, measurement):
                count = get_field_count(client, measurement, field)
                print(f"  # Field '{field}': {datatype} ({count})")

            for tag in get_tags(client, db, measurement):
                values = ','.join(get_tag_values(client, db, measurement, tag))
                print(f"  @ Tag '{tag}': {values}")
