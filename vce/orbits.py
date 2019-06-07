from datetime import datetime, timedelta
import click
from skyfield.api import EarthSatellite, load, utc
from .utils import parse, db_client
from math import radians, sin, cos, sqrt
import numpy as np
import matplotlib
matplotlib.use('pdf')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.animation import FuncAnimation


@click.group()
def orbits():
    """Satellite orbit propagation and plotting"""
    pass


@orbits.command()
@click.argument('config', type=click.File('r'))
def compute(config):
    """Compute and save satellite positions on the database.

    This command parses the YAML configuration in the CONFIG argument,
    computes satellite orbital positions, and stores them in the
    timeseries database. The position of base stations is also saved
    at a single time-point (the initial simulation time).
    """
    config = parse(config)
    client = db_client(config)

    start_time = config['system']['orbits']['start'].replace(tzinfo=utc)

    # save position of ground stations
    points = []
    for station in config['stations']:
        hostname = station['hostname']
        lat = station['lat']
        lon = station['lon']
        alt = station['alt']
        points.append({'measurement': 'pos',
                       'time': start_time,
                       'fields': {'lat': lat, 'lon': lon, 'alt': alt},
                       'tags': {'host': hostname}})
    client.write_points(points)

    # prepare observation times (precompute MT and gast)
    step = timedelta(minutes=config['system']['orbits']['step'])
    duration = timedelta(minutes=config['system']['orbits']['duration'])
    end_time = start_time + duration
    times = []
    t = start_time
    while t <= end_time:
        times.append(t)
        t += step

    ts = load.timescale()
    times_utc = ts.utc(times)
    times_utc.MT
    times_utc.gast

    # save position of satellites
    points = []
    for satellite in config['satellites']:
        hostname = satellite['hostname']
        tle1 = satellite['tle1']
        tle2 = satellite['tle2']
        pos = EarthSatellite(tle1, tle2).at(times_utc).subpoint()
        for t, lat, lon, alt in zip(times,
                                    pos.latitude.degrees,
                                    pos.longitude.degrees,
                                    pos.elevation.m):
            points.append({'measurement': 'pos',
                           'time': t,
                           'fields': {'lat': lat, 'lon': lon, 'alt': alt},
                           'tags': {'host': hostname}})
    client.write_points(points)


@orbits.command()
@click.argument('config', type=click.File('r'))
@click.argument('pdf_name', type=click.Path())
def plot2d(config, pdf_name):
    """Plot satellite positions from the database.

    This command parses the YAML configuration in the CONFIG argument,
    connects to the database, retrieves all satellite orbital
    positions (and base station locations), and plots them on a map.
    """
    config = parse(config)
    client = db_client(config)

    # query data and transpose for matplotlib
    results = client.query('SELECT lat, lon, alt FROM pos '
                           'GROUP BY host ORDER BY time')
    data = []
    for series in results.raw['series']:
        time, lat, lon, alt = [], [], [], []
        for t, lat_t, lon_t, alt_t in series['values']:
            time.append(datetime.fromisoformat(t[:-1]))
            lat.append(lat_t)
            lon.append(lon_t)
            alt.append(alt_t)
        data.append([series['tags']['host'], time, lat, lon, alt])

    # plot on a map
    matplotlib.rcParams['font.sans-serif'] = ['Roboto', 'Arial']
    import cartopy.crs as ccrs
    ax = plt.axes(projection=ccrs.PlateCarree())
    ax.coastlines(resolution='10m', linewidth=.4, color='#aaaaaa', zorder=-1)
    ax.set_extent([-180, 180, -90, 90])

    # ax.outline_patch.set_visible(False)
    ax.outline_patch.set_edgecolor('#0000006F')
    ax.outline_patch.set_linewidth(0.5)
    gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=True,
                      linewidth=0.1, color='#0000005F')
    import cartopy
    gl.xformatter = cartopy.mpl.gridliner.LONGITUDE_FORMATTER
    gl.yformatter = cartopy.mpl.gridliner.LATITUDE_FORMATTER
    gl.xlabel_style = {'size': 8, 'color': '#0000006F'}
    gl.ylabel_style = {'size': 8, 'color': '#0000006F'}

    # draw orbits
    for host, time, lat, lon, alt in data:
        size = [max(x/50000, 2) for x in alt]
        points = plt.scatter(lon, lat, s=size, alpha=0.5, linewidths=0,
                             transform=ccrs.PlateCarree())

        # annotate positions every 10 minutes
        color = points.get_facecolor()
        delta = timedelta(minutes=10)
        last = time[0]
        for t in range(len(time)):
            if t == 0 or (time[t]-last) >= delta:
                last = time[t]
                plt.scatter(lon[t], lat[t], s=size[t],
                            alpha=(1 if t == 0 else 0.6),
                            linewidths=0, color=color,
                            transform=ccrs.PlateCarree())
                text = host if t == 0 else ''
                if alt[t] > 1000:
                    text += (f"\n{time[t].strftime('%H:%M')} "
                             f"({alt[t]/1000:.1f} km)")
                if text:
                    plt.text(lon[t]+3, lat[t]-6, text,
                             fontsize=8, color=color[0][0:3])

    # draw latencies to most recent locations
    t = [0]*len(data)
    tmax = [len(time) for _, time, _, _, _ in data]
    min_time = -1
    while min_time is not None:
        for i in range(len(data)):
            for j in range(i):
                if len(data[i][1]) > 1 or len(data[j][1]) > 1:
                    p1 = np.array(ecef_xyz(data[i][2][t[i]],
                                           data[i][3][t[i]],
                                           data[i][4][t[i]]))
                    p2 = np.array(ecef_xyz(data[j][2][t[j]],
                                           data[j][3][t[j]],
                                           data[j][4][t[j]]))
                    latency = sight_latency(p1, p2)
                    if latency is not None:
                        plt.plot([data[i][3][t[i]], data[j][3][t[j]]],
                                 [data[i][2][t[i]], data[j][2][t[j]]],
                                 color='#FF00007F', linewidth=0.3)
        # advance time to next value
        min_hosts, min_time = [], None
        for i in range(len(t)):
            if t[i] + 1 < tmax[i]:
                next_time = data[i][1][t[i]+1]
                if not min_hosts or next_time < min_time:
                    min_hosts, min_time = [i], next_time
                elif next_time == min_time:
                    min_hosts.append(i)
        for i in min_hosts:
            t[i] += 1

    # save to file
    plt.savefig(pdf_name, bbox_inches='tight')


@orbits.command()
@click.argument('config', type=click.File('r'))
@click.argument('pdf_name', type=click.Path())
@click.option('--interactive', is_flag=True,
              help='Open in an interactive QT5 window')
def plot3d(config, pdf_name, interactive):
    """Plot satellite positions from the database in 3D.

    This command parses the YAML configuration in the CONFIG argument,
    connects to the database, retrieves all satellite orbital
    positions (and base station locations), and plots them in 3D.
    """
    config = parse(config)
    client = db_client(config)

    # query data and transpose for matplotlib
    results = client.query('SELECT lat, lon, alt FROM pos '
                           'GROUP BY host ORDER BY time')
    data = []
    for series in results.raw['series']:
        time, x, y, z = [], [], [], []
        for t, lat_t, lon_t, alt_t in series['values']:
            time.append(datetime.fromisoformat(t[:-1]))
            x_t, y_t, z_t = ecef_xyz(lat_t, lon_t, alt_t)
            x.append(x_t)
            y.append(y_t)
            z.append(z_t)
        data.append([series['tags']['host'], time, x, y, z])

    # plot a reference ellipsoid
    matplotlib.use('Qt5Agg')
    matplotlib.rcParams['font.sans-serif'] = ['Roboto', 'Arial']
    ax = plt.axes(projection='3d')
    ax.set_aspect('equal')
    ax.set_xlim(-9000, 9000)
    ax.set_ylim(-9000, 9000)
    ax.set_zlim(-9000, 9000)
    plt.subplots_adjust(left=0, right=1, bottom=0, top=1)
    earth_ellipsoid(ax)

    # plot orbits
    for host, time, x, y, z in data:
        points = ax.scatter(x, y, z)

        # annotate positions every 10 minutes
        color = points.get_facecolor()
        delta = timedelta(minutes=10)
        last = time[0]
        for t in range(len(time)):
            if t == 0 or (time[t]-last) >= delta:
                last = time[t]
                ax.scatter(x[t], y[t], z[t],
                           alpha=(1 if t == 0 else 0.6),
                           linewidths=0, color=color)
                text = host if t == 0 else ''
                if len(time) > 1:
                    text += f"\n{time[t].strftime('%H:%M')}"
                if text:
                    ax.text(x[t]+6, y[t]+6, z[t]+6, text,
                            fontsize=10, color=color[0][0:3])

    # draw latencies to most recent locations
    t = [0]*len(data)
    tmax = [len(time) for _, time, _, _, _ in data]
    min_time = -1
    while min_time is not None:
        for i in range(len(data)):
            for j in range(i):
                if len(data[i][1]) > 1 or len(data[j][1]) > 1:
                    p1 = [data[i][d][t[i]] for d in range(2, 5)]
                    p2 = [data[j][d][t[j]] for d in range(2, 5)]
                    latency = sight_latency(p1, p2)
                    if latency is not None:
                        ax.plot([data[i][2][t[i]], data[j][2][t[j]]],
                                [data[i][3][t[i]], data[j][3][t[j]]],
                                [data[i][4][t[i]], data[j][4][t[j]]],
                                color='#FF00006F', linewidth=1.0)
        # advance time to next value
        min_hosts, min_time = [], None
        for i in range(len(t)):
            if t[i] + 1 < tmax[i]:
                next_time = data[i][1][t[i]+1]
                if not min_hosts or next_time < min_time:
                    min_hosts, min_time = [i], next_time
                elif next_time == min_time:
                    min_hosts.append(i)
        for i in min_hosts:
            t[i] += 1

    if interactive:
        plt.show()
    else:
        plt.savefig(pdf_name, bbox_inches='tight')


wgs84_a, wgs84_b = 6378.137, 6356.7523142452  # WGS84 semi-major/minor axes
wgs84_f = 1-wgs84_b/wgs84_a                   # flattening
wgs84_ecc2 = wgs84_f*(2-wgs84_f)              # squared eccentricity


def ecef_xyz(lat, lon, alt):
    # see: agamenon.tsc.uah.es/Asignaturas/it/rd/apuntes/RxControl_Manual.pdf
    # checked against: https://www.ngs.noaa.gov/NCAT/
    # lat, lon in degrees, alt in meters
    alt = alt/1000  # all calculations in km
    phi, lam = radians(lat), radians(lon)
    sphi, cphi = sin(phi), cos(phi)
    slam, clam = sin(lam), cos(lam)
    r = wgs84_a/sqrt(1-wgs84_ecc2*sphi*sphi)
    x = (alt+r)*cphi*clam
    y = (alt+r)*cphi*slam
    z = (alt+r*(1-wgs84_ecc2))*sphi
    return x, y, z


def earth_ellipsoid(ax):
    ax.set_xlabel('x (km)', color='#0000006F')
    ax.set_ylabel('y (km)', color='#0000006F')
    ax.set_zlabel('z (km)', color='#0000006F')
    ax.xaxis.line.set_color('#0000006F')
    ax.yaxis.line.set_color('#0000006F')
    ax.zaxis.line.set_color('#0000006F')
    ax.tick_params(axis='x', colors='#0000006F')
    ax.tick_params(axis='y', colors='#0000006F')
    ax.tick_params(axis='z', colors='#0000006F')
    ax.xaxis._axinfo['tick']['color'] = '#0000001F'
    ax.yaxis._axinfo['tick']['color'] = '#0000001F'
    ax.zaxis._axinfo['tick']['color'] = '#0000001F'
    ax.xaxis._axinfo['grid']['color'] = '#0000001F'
    ax.yaxis._axinfo['grid']['color'] = '#0000001F'
    ax.zaxis._axinfo['grid']['color'] = '#0000001F'
    ax.xaxis.set_pane_color((0, 0, 0, 0.01))
    ax.yaxis.set_pane_color((0, 0, 0, 0.01))
    ax.zaxis.set_pane_color((0, 0, 0, 0.01))

    theta = np.linspace(0, 2.0 * np.pi, 201)
    cost, sint, zeros = np.cos(theta), np.sin(theta), np.zeros_like(theta)
    lon0 = wgs84_a * np.vstack((cost, zeros, sint))

    meridians = []
    for phi in np.linspace(0.0, np.pi, 16):
        cosp, sinp = np.cos(phi), np.sin(phi)
        meridians.append(np.vstack((lon0[0] * cosp - lon0[1] * sinp,
                                    lon0[1] * cosp + lon0[0] * sinp, lon0[2])))
    for x, y, z in meridians:
        ax.plot(x, y, z*(wgs84_b/wgs84_a),
                color='gray', linewidth=1.0, alpha=0.5)

    parallels = []
    for phi in np.linspace(-np.pi/2.0, np.pi/2.0, 21):
        cosp, sinp = np.cos(phi), np.sin(phi)
        parallels.append(wgs84_a*np.vstack((cost*cosp, sint*cosp, zeros+sinp)))
    for x, y, z in parallels:
        ax.plot(x, y, z*(wgs84_b/wgs84_a),
                color='gray', linewidth=1.0, alpha=0.5)


axes = np.array([wgs84_a, wgs84_a, wgs84_b])
speed = 299792458.0


def sight_latency(p1, p2):
    p1, p2 = np.array(p1), np.array(p2)
    dist = np.linalg.norm(p1-p2)
    if dist < 5:  # distance less than 5 km, no latency
        return 0.0
    s1, s2 = p1/axes, p2/axes
    s12 = s1-s2
    a = np.dot(s12, s12)
    b = np.sum(np.dot(s12, s2))*2
    c = np.dot(s2, s2)-1
    d = b**2 - 4*a*c
    if d < 0.0:
        return dist/speed*1000  # no intersection
    else:
        q = (-b-np.sign(b)*np.sqrt(d))/2
        sol1 = q/a
        sol2 = c/q
        if (sol1 < 0.0 or sol1 > 1.0) and \
           (sol2 < 0.0 or sol2 > 1.0):
            return dist/speed*1000  # outside of segment
        else:
            return None  # no line of sight


@orbits.command()
@click.argument('config', type=click.File('r'))
@click.argument('gif_name', type=click.Path())
@click.option('--interactive', is_flag=True,
              help='Open in an interactive QT5 window')
def animate(config, gif_name, interactive):
    """Animate satellite positions from the database in 3D.

    This command parses the YAML configuration in the CONFIG argument,
    connects to the database, retrieves all satellite orbital
    positions (and base station locations), and animates them.
    """
    config = parse(config)
    client = db_client(config)
    sats = set((sat['hostname'] for sat in config['satellites']))

    # prepare list of simulation times
    start_time = config['system']['orbits']['start']
    step = timedelta(minutes=config['system']['orbits']['step'])
    duration = timedelta(minutes=config['system']['orbits']['duration'])
    end_time = start_time + duration
    times = []
    t = start_time
    while t <= end_time:
        times.append(t)
        t += step

    # plot a reference ellipsoid
    matplotlib.use('Qt5Agg')
    matplotlib.rcParams['font.sans-serif'] = ['Roboto', 'Arial']
    ax = plt.axes(projection='3d')
    ax.set_aspect('equal')
    ax.set_xlim(-9000, 9000)
    ax.set_ylim(-9000, 9000)
    ax.set_zlim(-9000, 9000)
    plt.subplots_adjust(left=0, right=1, bottom=0, top=1)
    earth_ellipsoid(ax)
    title = plt.gcf().text(0.05, 0.05, '', color='#0000006F')

    def update(time):
        for c in ax.get_children():
            if c.get_gid() == 'frame':
                c.remove()
        plt.gca().set_prop_cycle(None)

        time_str = time.isoformat()
        title.set_text(time_str)
        results = client.query("SELECT lat, lon, alt FROM pos "
                               f"WHERE time <= '{time_str}Z' GROUP BY host "
                               "ORDER BY time DESC LIMIT 1")
        data = []
        for series in results.raw['series']:
            host = series['tags']['host']
            time, lat, lon, alt = series['values'][0]
            time = datetime.fromisoformat(time[:-1])
            x, y, z = ecef_xyz(lat, lon, alt)
            points = ax.scatter(x, y, z, gid='frame')
            color = points.get_facecolor()[0][0:3]
            ax.text(x+6, y+6, z+6, host, gid='frame',
                    fontsize=15, color=color)
            data.append([host, time, x, y, z])

        for i in range(len(data)):
            for j in range(i):
                if data[i][0] in sats or data[j][0] in sats:
                    p1 = np.array([data[i][d] for d in range(2, 5)])
                    p2 = np.array([data[j][d] for d in range(2, 5)])
                    latency = sight_latency(p1, p2)
                    if latency is not None:
                        ax.plot([data[i][2], data[j][2]],
                                [data[i][3], data[j][3]],
                                [data[i][4], data[j][4]],
                                color='#FF00006F',
                                linewidth=1.0, gid='frame')
                        halfway = (p1+p2)/2 + 6
                        ax.text(*halfway, f'{latency*1000:.1f}',
                                fontsize=10, color='#FF00006F', gid='frame')

    animation = FuncAnimation(plt.gcf(), update, times,
                              interval=1000, blit=False, repeat=False)

    if interactive:
        plt.show()
    else:
        animation.save(gif_name, writer='imagemagick')


def get_delays(client, t, src):
    """Get delays from a given source and time to all destinations."""

    # last timepoint before t
    results = client.query(f'SELECT lat, lon, alt FROM pos '
                           f"WHERE time <= '{t.isoformat()}Z' "
                           f'GROUP BY host ORDER BY time DESC LIMIT 1')

    pos = {}
    for series in results.raw['series']:
        assert len(series['values']) == 1
        host = series['tags']['host']
        time, lat, lon, alt = series['values'][0]
        pos[host] = np.array(ecef_xyz(lat, lon, alt))

    if src not in pos:
        raise ValueError(f'Host {src} not found in orbits timeseries')

    return {dst: sight_latency(pos[src], pos[dst])
            for dst in pos if dst != src}
