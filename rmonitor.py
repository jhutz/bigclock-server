# Copyright (c) 2018 Jeffrey Hutzelman
# All Rights Reserved.
# See LICENSE for licensing terms.

"""RMONITOR Protocol Support

Thus module contains tools for receiving, dispatching, caching, processing,
and relaying RMONITOR protocol reports.

Classes:

- RMonitorReport            RMONITOR report; has these subclasses:
  - RMonitor_Entry            Entry Data ($A)
  - RMonitor_Run              Run Info ($B)
  - RMonitor_Class            Class Info ($C)
  - RMonitor_Competitor       Competitor Data ($COMP)
  - RMonitor_ExtraInfo        Extra Info ($E)
  - RMonitor_Flag             Flag / Run State ($F)
  - RMonitor_PositionData     Race Position Report ($G)
  - RMonitor_LapTimeData      Practice/Qualifying Report ($H)
  - RMonitor_Reset            Initialization ($I)
  - RMonitor_PassingData      Passing Report ($J)
  - RMonitor_LineCrossing     Line Crossing Report ($L) [IMSA]
  - RMonitor_TrackInfo        Line Crossing Report ($L) [IMSA]
- RMonitorCache             Cache of information received since start of run
"""

import time
import codecs
import csv
import json
import io
import asyncio
import asyncio_dispatch
import logging

class RMonitorReport:
    """RMONITOR protocol report.

    Class Methods:
    - create        Create a new report from a field list, with auto-subclassing..
    - from_csv      Create a new report from a line of CSV data.
    - from_json     Create a new report from a JSON array.
    - subscribe     Add a callback to receive report signals.
    - unsubscribe   Remove a report signal callback.

    Instance Methods:
    - as_csv        Convert report to a line of CSV data.
    - as_json       Convert report to a JSON array.
    - cache_key     Return a suitable key for caching this report.
    - signal        Send a signal about this report.

    Instance Variables:
    - kind          String describing the kind of record (the first field)
    - fields        Tuple of fields from the original report
    """

    __types = {}
    @classmethod
    def register(cls, type):
        """Designate an RMonitor report type subclass to be auto-registered."""
        def _register(subclass):
            cls.__types[type] = subclass
            return subclass
        return _register

    @classmethod
    def create(cls, data, strict=False, csv_text=None, json_text=None):
        """Create a new RMONITOR report.

        This creates an RMONITOR report object of the appropriate type,
        depending on the provided data (list of fields).
        
        If strict is True, the data must describe a known report type and
        include enough fields for that type, and the fields must be of the
        correct type; otherwise, an appropriate exception will be raised. 

        If strict is False (the default), unknown report types or invalid
        data will not result in an exception; instead, a generic object
        will be returned.
        """
        kind = data[0]
        try:
            if kind not in cls.__types:
                raise ValueError("Unrecognized RMonitor sentence type %s" % kind)
            return cls.__types[kind](data)
        except ValueError:
            if strict: raise
        except IndexError:
            if strict: raise
        return cls(data)

    @classmethod
    def from_csv(cls, text, strict=False, charset='cp1252'):
        """Create a new RMONTIOR report from CSV data.

        This creates an RMONITOR report object of the appropriate type,
        depending on the provided data. Operation is as for create(),
        except that the input is a string containing a single CSV row.
        """
        if charset is not None:
            text = codecs.decode(text, charset)
        data = next(csv.reader([text]))
        return cls.create(data, strict=strict, csv_text=text)

    @classmethod
    def from_json(cls, text, strict=False):
        """Create a new RMONITOR report from a JSON array.

        This creates an RMONITOR report object of the appropriate type,
        depending on the provided data. Operation is as for create(),
        except that the input is a string containing a JSON array.
        """
        return cls.create(json.loads(text), strict=strict, json_text=text)

    def __init__(self, data, csv_text=None, json_text=None):
        """Create a new RMONITOR report.

        This creates a new RMONITOR report based on the provided data.
        This constructor should not normally be called directly; instead,
        use the class methods create(), from_csv(), or from_json() to
        automatically create an object of the appropriate subclass.

        The csv_text and json_text, if given, are used to seed cached
        representations of the data in those formats. They should not
        normally be provided except when creating a record from one of
        those formats.
        """
        self.fields = tuple(data)
        self.kind = self.fields[0]
        self._csv = csv_text
        self._json = json_text
        self._setup()

    def _setup(self): pass

    def as_csv(self, charset='cp1252'):
        """Encode this report as an RMONITOR CSV record."""
        if self._csv is None:
            fields = list(self.fields)
            if self.kind == '$F' and len(fields) > 5:
                # KLUDGE: CSV expects the flag state to be space-padded
                fields[5] = "%-6s" % fields[5]
            s = io.StringIO(newline='')
            cw = csv.writer(s)
            cw.writerow(fields)
            self._csv = s.getvalue()
            s.close()
        if charset is None: return self._csv
        return codecs.encode(self._csv, charset, errors='replace')

    def as_json(self):
        """Encode this report as a JSON array."""
        if self._json is None:
            self._json = json.dumps(self.fields)
        return self._json

    def cache_key(self):
        """Return a key used for caching this report, or None."""
        if not hasattr(self, '_ckey'):
            return None
        return self._ckey(self.fields)

    @classmethod
    def cache_key_for_data(cls, data):
        kind = data[0]
        if kind not in cls.__types:
            return None
        if not hasattr(cls.__types[kind], '_ckey'):
            return None
        return cls.__types[kind]._ckey(data)

    @staticmethod
    def _ckey_single(fields):
        """Return a cache key for a singleton report.
        
        This key form is based only on the report type. It is used for report
        types which contain global state, for which every report replaces the
        previous data of the same type.
        """
        return fields[0]

    @staticmethod
    def _ckey_mapping(fields):
        """Return a cache key for a mapping-type report.
        
        This key form is based on the report type and first data field.  It is
        used for report types containing information about a particular entity,
        such as a competitor, where new reports replace only the previous data
        for the same entity.
        """
        return '%s:%s' % (fields[0], fields[1])

    @staticmethod
    def _ckey_list(fields):
        """Return a cache key for an indexed report.
        
        This key form is based on the report type and first data field and
        formats the data field as an integer, allowing cache data to be sorted
        numerically.  It is used for report types describing a series of
        numbered, ordered rows, such as race position information, where each
        new report replaces only the previous data for the same row.
        """
        return '%s#%06d' % (fields[0], int(fields[1]))

    __signal = None

    @classmethod
    async def subscribe(cls, callback, types=None, signal=None):
        """Subscribe to the specified (or all) RMONITOR report types."""
        if signal is None and cls.__signal is None:
            cls.__signal = asyncio_dispatch.Signal(report=None)
        if signal is None:
            signal = cls.__signal
        await signal.connect(callback, keys=types)

    @classmethod
    async def unsubscribe(cls, callback, types=None, signal=None):
        """Unsubscribe from the specified (or all) RMONITOR report types."""
        if signal is None and cls.__signal is None:
            return
        if signal is None:
            signal = cls.__signal
        await signal.disconnect(callback, keys=types)

    async def signal(self, signal=None):
        """Send a signal reporting this event."""
        if signal is None and self.__signal is None:
            return
        if signal is None:
            signal = self.__signal
        await signal.send(key=self.kind, report=self)

    class Subscription:
        def __init__(self, callback, types=None, signal=None):
            self._callback = callback
            self._types    = types
            self._signal   = signal

        async def __aenter__(self):
            await RMonitorReport.subscribe(self._callback,
                    self._types, self._signal)

        async def __aexit__(self, exc_type, exc_value, traceback):
            await RMonitorReport.unsubscribe(self._callback,
                    self._types, self._signal)


@RMonitorReport.register('$A')
class RMonitor_Entry(RMonitorReport):
    """RMONITOR Entry Data ($A)

    Additional Instance Variables:
    - id            Competitor ID
    - car           Car number
    - txno          Transponder number
    - first_name    Driver's first name
    - last_name     Driver's last name
    - extra         First "additional data" field
    - clsid         Class ID
    """
    _ckey = staticmethod(RMonitorReport._ckey_mapping)
    def _setup(self):
        self.id         = self.fields[1]
        self.car        = self.fields[2]
        self.txno       = self.fields[3]
        self.first_name = self.fields[4]
        self.last_name  = self.fields[5]
        self.extra      = self.fields[6]
        self.clsid      = self.fields[7]

@RMonitorReport.register('$B')
class RMonitor_Run(RMonitorReport):
    """RMONITOR Run Info ($B)

    Additional Instance Variables:
    - id            Run ID (integer)
    - run_name      Name of run
    - is_active     True iff this is an active run
    """
    _ckey = staticmethod(RMonitorReport._ckey_single)
    def _setup(self):
        self.id         = int(self.fields[1])
        self.run_name   = self.fields[2]
        self.is_active  = self.id != 95

@RMonitorReport.register('$C')
class RMonitor_Class(RMonitorReport):
    """RMONITOR Class Info ($C)

    Additional Instance Variables:
    - id            Class ID
    - class_name    Name of class
    """
    _ckey = staticmethod(RMonitorReport._ckey_mapping)
    def _setup(self):
        self.id         = self.fields[1]
        self.class_name = self.fields[2]

@RMonitorReport.register('$COMP')
class RMonitor_Competitor(RMonitorReport):
    """RMONITOR Competitor Data ($COMP)

    Additional Instance Variables:
    - id            Competitor ID
    - car           Car number
    - clsid         Class ID
    - first_name    Driver's first name
    - last_name     Driver's last name
    - extra         First "additional data" field
    - extra2        Second "additional data" field
    """
    _ckey = staticmethod(RMonitorReport._ckey_mapping)
    def _setup(self):
        self.id         = self.fields[1]
        self.car        = self.fields[2]
        self.clsid      = self.fields[3]
        self.first_name = self.fields[4]
        self.last_name  = self.fields[5]
        self.extra      = self.fields[6]
        self.extra2     = self.fields[7]

@RMonitorReport.register('$E')
class RMonitor_ExtraInfo(RMonitorReport):
    """RMONITOR Extra Info ($E)

    Additional Instance Variables:
    - extra_key     Extra data item key
    - extra_value   Extra data item value
    """
    _ckey = staticmethod(RMonitorReport._ckey_mapping)
    def _setup(self):
        self.extra_key    = self.fields[1]
        self.extra_value  = self.fields[2]

@RMonitorReport.register('$F')
class RMonitor_Flag(RMonitorReport):
    """RMONITOR Flag / Run State ($F)

    Additional Instance Variables:
    - laps_left     Laps remaining, or None
    - time_left     Time remaining, or None
    - tod           Time of day
    - elapsed       Elapsed time
    - flag          Flag condition
    """
    _ckey = staticmethod(RMonitorReport._ckey_single)
    def _setup(self):
        self.laps_left  = int(self.fields[1])
        self.time_left  = self.fields[2]
        self.tod        = self.fields[3]
        self.elapsed    = self.fields[4]
        self.flag       = self.fields[5].strip()
        if self.laps_left == 9999:       self.laps_left = None
        if self.time_left == "00:00:00": self.time_left = None

@RMonitorReport.register('$G')
class RMonitor_PositionData(RMonitorReport):
    """RMONITOR Race Position Report ($G)

    Additional Instance Variables:
    - pos           Position (integer)
    - id            Competitor ID
    - laps          Laps completed
    - time          Total time
    """
    _ckey = staticmethod(RMonitorReport._ckey_list)
    def _setup(self):
        self.pos    = int(self.fields[1])
        self.id     = self.fields[2]
        self.laps   = 0 if self.fields[3] == '' else int(self.fields[3])
        self.time   = self.fields[4]

@RMonitorReport.register('$H')
class RMonitor_LapTimeData(RMonitorReport):
    """RMONITOR Practice/Qualifying Report ($H)

    Additional Instance Variables:
    - pos           Position (integer)
    - id            Competitor ID
    - best_lap      Best lap, or None
    - best_time     Best lap time, or None
    """
    _ckey = staticmethod(RMonitorReport._ckey_list)
    def _setup(self):
        self.pos       = int(self.fields[1])
        self.id        = self.fields[2]
        self.best_lap  = 0 if self.fields[3] == '' else int(self.fields[3])
        self.best_time = self.fields[4]
        if self.best_lap == 0 or self.best_time == "00:00:00.000":
            self.best_lap  = None
            self.best_time = None

@RMonitorReport.register('$I')
class RMonitor_Reset(RMonitorReport):
    """RMONITOR Initialization ($I)

    Additional Instance Variables:
    - tod           Time of day
    - date          Date
    """
    @staticmethod
    def _ckey(fields): return ''
    def _setup(self):
        self.tod        = self.fields[1]
        self.date       = self.fields[2]

@RMonitorReport.register('$J')
class RMonitor_PassingData(RMonitorReport):
    """RMONITOR Passing Report ($J)

    Additional Instance Variables:
    - id            Competitor ID
    - last_lap      Last lap time, or None
    - time          Total time
    """
    _ckey = staticmethod(RMonitorReport._ckey_mapping)
    def _setup(self):
        self.id        = self.fields[1]
        self.last_lap  = self.fields[2]
        self.time      = self.fields[3]
        if self.last_lap == "00:00:00.000":
            self.last_lap = None

@RMonitorReport.register('$L')
class RMonitor_LineCrossing(RMonitorReport):
    """RMONITOR Line Crossing Report ($L) [IMSA]

    Additional Instance Variables:
    - car           Car number
    - loop_num      Loop number (integer)
    - loop_name     Loop designation
    - date          Date of passing
    - time          Time of passing
    - driver_id     Driver number (integer), or None
    - class_name    Name of class
    """
    def _setup(self):
        self.car        = self.fields[1]
        self.loop_num   = int(self.fields[2])
        self.loop_name  = self.fields[3]
        self.date       = self.fields[4]
        self.time       = self.fields[5]
        self.driver_id  = int(self.fields[6])
        self.class_name = self.fields[7]
        if self.driver_id == 0:
            self.driver_id = None

@RMonitorReport.register('$T')
class RMonitor_TrackInfo(RMonitorReport):
    """RMONITOR Line Crossing Report ($L) [IMSA]

    Additional Instance Variables:
    - track_name    Name of track
    - track_nick    Track short name
    - track_dist    Track distance (miles)
    - sections      List of sections

    Each section is represented by a dict containing these fields:
    - name          Section designator
    - start         Designator of starting timeline
    - end           Designator of ending timeline
    - dist          Distance (inches)
    """
    _ckey = staticmethod(RMonitorReport._ckey_single)
    def _setup(self):
        self.track_name = self.fields[1]
        self.track_nick = self.fields[2]
        self.track_dist = self.fields[3]
        self.sections = [ {
            name:  self.fields[4*i + 5],
            start: self.fields[4*i + 6],
            end:   self.fields[4*i + 7],
            dist:  self.fields[4*i + 8]
            } for i in range(int(self.fields[4]))
            ]


class RMonitorCache:
    __default_cache = None

    @classmethod
    def get_cache(cls):
        """Return the global default RMONITOR cache."""
        if cls.__default_cache is None:
            cls.__default_cache = cls()
        return cls.__default_cache

    def __init__(self):
        """Create a new RMONITOR cache."""
        self._cache = {}

    def update(self, report):
        """Update the cache with a new report."""
        if report.kind == '$I': self._cache = {}
        key = report.cache_key()
        if key is not None:
            self._cache[key] = report

    def lookup(self, kind, key=None):
        """Fetch a specified report from the cache."""
        key = RMonitorReport.cache_key_for_data([kind, key])
        if key is None:
            return None
        if key not in self._cache:
            return None
        return self._cache[key]

    def contents(self):
        """Retrieve a sorted list of all reports in the cache."""
        return [ v for (k,v) in sorted(self._cache.items()) ]

    async def auto_update(self, signal=None):
        """Enable signal-based automatic cache updates.

        Enable automatic updating of the cache based on signals sent by
        RMonitorReport.signal() via the specified signal dispatcher, or
        via RMonitorReport's default dispatcher if signal is None.
        """
        await RMonitorReport.subscribe(self._signal_cb, signal=signal)

    async def stop_auto_update(self, signal=None):
        """Disable signal-based automatic cache updates.

        Disable automatic updating of the cache based on signals sent by
        RMonitorReport.signal() via the specified signal dispatcher, or
        via RMonitorReport's default dispatcher if signal is None.
        """
        await RMonitorReport.unsubscribe(self._signal_cb, signal=signal)

    async def _signal_cb(self, report, **kw):
        """Signal callback for automatic cache updates."""
        self.update(report)


class _StreamDiscarder(asyncio.StreamReader):
    """Like StreamReader, except all the incoming data is discarded."""
    def feed_data(self, data): pass


class RMonitorRelayClient(asyncio.StreamReaderProtocol):
    def __init__(self, cache=None, signal=None):
        self._signal = signal
        if cache is None:
            cache = RMonitorCache.get_cache()
        self._queue = asyncio.Queue()
        for report in cache.contents():
            self._queue.put_nowait(report)
        super().__init__(_StreamDiscarder(), self._connected)

    async def _connected(self, reader, writer):
        """Connection established callback."""
        self._sender_task = asyncio.Task.current_task()
        async with RMonitorReport.Subscription(self._signal_cb, signal=self._signal):
            try:
                while True:
                    report = await self._queue.get()
                    writer.write(report.as_csv())
                    self._queue.task_done()
            except asyncio.CancelledError: pass

    async def _signal_cb(self, report, **kw):
        """Signal callback"""
        await self._queue.put(report)

    def connection_lost(self, exc):
        """Connection lost callback."""
        self._sender_task.cancel()
        super().connection_lost(exc)


class RMonitorRelay:
    def __init__(self, host=None, port=50000, cache=None, signal=None):
        self.host   = host
        self.port   = port
        self.cache  = cache
        self.signal = signal
        self.server = None

    def factory(self):
        return RMonitorRelayClient(cache=self.cache, signal=self.signal)

    async def _start(self):
        loop = asyncio.get_event_loop()
        self.server = await loop.create_server(self.factory, self.host, self.port)

    def start_server(self):
        asyncio.ensure_future(self._start())

    def stop_server(self):
        if self.server is not None:
            self.server.close()
            self.server = None

    # XXX add operations for changing the host and/or port with auto-restart


class RMonitorCollector():
    """RMONITOR data stream collector.

    This manages a connection to an RMONITOR data source, reading and processing
    individual reports, feeding them to interested parties, timing out when the
    connection has been idle too long, and so on. In most cases, only one active
    collector should be feeding a signal source at any given time.

    The connect() method is provided to simplify connecting to a data source
    (pull mode), reading all available data, and returning when done.
   """

    def __init__(self, signal=None):
        self.signal  = signal
        self.server = None
        self.puller = None
        self.conns  = []

    async def connect(self, host, port=50000):
        reader, writer = await asyncio.open_connection(host, port)
        await self._worker(reader, writer)

    async def start_server(self, host=None, port=40000):
        self._stop()
        self.server = await asyncio.start_server(self._connected, host, port)

    async def start_pull(self, host, port=50000):
        self._stop()
        loop = asyncio.get_event_loop()
        self.puller = loop.create_task(self._puller(host, port))

    async def _puller(self, host, port):
        while True:
            reader, writer = await asyncio.open_connection(host, port)
            self._connected(reader, writer)
            #XXX wait

    def stop(self):
        self._stop()
        for task in self.conns:
            task.cancel()
        self.conns = []

    def _stop(self):
        if self.server is not None:
            self.server.close()
            self.server = None
        if self.puller is not None:
            self.puller.cancel()
            self.puller = None

    def _connected(self, reader, writer):
        loop = asyncio.get_event_loop()
        conns.append(loop.create_task(self._worker(reader, writer)))

    async def _worker(self, reader, writer):
        """Connection established callback."""
        #XXX sanity check
        #XXX takeover as data source
        while True:
            try:
                text = await reader.readline()
            except ValueError:
                continue
            if len(text) == 0: break
            if text == b'\n': continue
            await RMonitorReport.from_csv(text).signal(self.signal)


async def _heartbeat():
    now = time.strftime('%H:%M:%S')
    today = time.strftime('%d %b %y')
    await RMonitorReport.create(['$I', now, today]).signal()
    data = ['$F', 9999, '00:00:00', now, '00:59:59.999','Green ']
    while True:
        data[3] = time.strftime('%H:%M:%S')
        await RMonitorReport.create(data).signal()
        await asyncio.sleep(1)

async def _rmonitor_test():
    cache = RMonitorCache.get_cache()
    await cache.auto_update()
    server = RMonitorRelay()
    server.start_server()
    await _heartbeat()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    logging.basicConfig(level=logging.DEBUG)
    asyncio.ensure_future(_rmonitor_test())
    loop.run_forever()
