VCE: Virtual Constellation Engine
-------------------------------------

``vce`` is a cloud framework to prototype and emulate satellite applications.

It provides support for orbits calculation, network latency/bandwidth
emulation, instrument control by the application, and constellation
monitoring (positions, CPU/memory/disk/network usage, configuration
changes made to the emulated onboard instruments).

The state of everything in the constellation is saved in a time series
database (`InfluxDB <https://github.com/influxdata/influxdb>`_).
This database can be inspected after running the emulation scenario.

- Each satellite runs in an AWS instance which is part of an AWS
  CloudFormation stack.

- Networking parameters are set (through
  `tcconfig <https://tcconfig.readthedocs.io/en/latest/>`_ and the
  `netem <https://wiki.linuxfoundation.org/networking/netem>`_
  component of the Linux kernel) by ``vce agent``, which runs on each
  node and polls the current value of the parameters from the time
  series database.

- Networking parameters are saved in the database by ``vce links`` in
  real-time.

- Satellite positions are stored in advance by ``vce orbits``, which
  is run at the beginning of the emulation.

- Resource usage measurements are collection on each AWS instance by
  running `collectd <https://collectd.org/>`_ and sending the data to
  InfluxDB.

- Timeseries of usage measurements, satellite positions (on a map),
  and instruments state can be visualized and analyzed using `grafana
  <https://grafana.com/>`_.


Development
-----------

To install all development dependencies, just clone this project and
then run:

.. code:: bash

   make init

This will create a Python 3.7 virtual environment using ``pipenv``.
