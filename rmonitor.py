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


import codecs
import csv
import json
import io
import asyncio_dispatch

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
    - report        Send a signal about this report.

    Instance Variables:
    - kind          String describing the kind of record (the first field)
    - fields        Tuple of fields from the original report
    """

    ## Registration and decorators
    __types = {}
    @classmethod
    def register(cls, type):
        """Register an RMonitor report type subclass."""
        def _register(subclass):
            cls.__types[type] = subclass
            return subclass
        return _register

    @classmethod
    def single_key(cls, subclass):
        """Declare an RMonitor report type to use no subkey."""
        subclass.cache_key = subclass._ckey_single
        return subclass

    @classmethod
    def string_key(cls, subclass):
        """Declare an RMonitor report type to use a string subkey."""
        subclass.cache_key = subclass._ckey_str
        return subclass

    @classmethod
    def int_key(cls, subclass):
        """Declare an RMonitor report type to use an integer subkey."""
        subclass.cache_key = subclass._ckey_int
        return subclass


    ## Creation from various data forms, with automatic subclassing
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
    def from_json(cls, text, strict=False):
        """Create a new RMONITOR report from a JSON array.

        This creates an RMONITOR report object of the appropriate type,
        depending on the provided data. Operation is as for create(),
        except that the input is a string containing a JSON array.
        """
        return cls.create(json.loads(text), strict=strict, json_text=text)

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
        return cls.create(row, strict=strict, csv_text=text)


    ## Initialization
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


    ## Caching key generation
    def cache_key(self):
        """Return a key used for caching this report, or None.
        
        The returned key in this case is None, indicating the record should
        not be cached.
        """
        return None

    def _ckey_single(self):
        """Return a key used for caching this report, or None.
        
        This key form is based only on the report type. It is used for report
        types which contain global state, for which every report replaces the
        previous data of the same type.
        """
        return self.kind

    def _ckey_str(self):
        """Return a key used for caching this report, or None.
        
        This key form is based on the report type and first data field.  It is
        used for report types containing information about a particular entity,
        such as a competitor, where new reports replace only the previous data
        for the same entity.
        """
        return '%s:%s' % (self.kind, self.fields[1])

    def _ckey_int(self):
        """Return a key used for caching this report, or None.
        
        This key form is based on the report type and first data field and
        formats the data field as an integer, allowing cache data to be sorted
        numerically.  It is used for report types describing a series of
        numbered, ordered rows, such as race position information, where each
        new report replaces only the previous data for the same row.
        """
        return '%s#%06d' % (self.kind, int(self.fields[1]))


    ## Output generation
    def as_csv(self, charset='cp1252')
        """Encode this report as an RMONITOR CSV record."""
        if self._csv is None:
            s = io.StringIO(newline='')
            cw = csv.writer(s)
            cw.writerow(self.fields)
            self._csv = s.getvalue()
            s.close()
        if charset is None: return self._csv
        return codecs.encode(self._csv, charset, errors='replace')

    def as_json(self):
        """Encode this report as a JSON array."""
        if self._json is None:
            self._json = json.dumps(self.fields)
        return self._json


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

    async def report(self, signal=None):
        """Send a signal reporting this event."""
        if signal is None and self.__signal is None:
            return
        if signal is None:
            signal = self.__signal
        await signal.send(key=self.kind, report=self)


@RMonitorReport.register('$A')
@RMonitorReport.string_key
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
    def _setup(self):
        self.id         = self.fields[1]
        self.car        = self.fields[2]
        self.txno       = self.fields[3]
        self.first_name = self.fields[4]
        self.last_name  = self.fields[5]
        self.extra      = self.fields[6]
        self.clsid      = self.fields[7]

@RMonitorReport.register('$B')
@RMonitorReport.single_key
class RMonitor_Run(RMonitorReport):
    """RMONITOR Run Info ($B)

    Additional Instance Variables:
    - id            Run ID (integer)
    - run_name      Name of run
    - is_active     True iff this is an active run
    """
    def _setup(self):
        self.id         = int(self.fields[1])
        self.run_name   = self.fields[2]
        self.is_active  = self.id != 95

@RMonitorReport.register('$C')
@RMonitorReport.int_key
class RMonitor_Class(RMonitorReport):
    """RMONITOR Class Info ($C)

    Additional Instance Variables:
    - id            Class ID (integer)
    - class_name    Name of class
    """
    def _setup(self):
        self.id         = self.fields[1]
        self.class_name = self.fields[2]

@RMonitorReport.register('$COMP')
@RMonitorReport.string_key
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
    def _setup(self):
        self.id         = self.fields[1]
        self.car        = self.fields[2]
        self.clsid      = self.fields[3]
        self.first_name = self.fields[4]
        self.last_name  = self.fields[5]
        self.extra      = self.fields[6]
        self.extra2     = self.fields[7]

@RMonitorReport.register('$E')
@RMonitorReport.string_key
class RMonitor_ExtraInfo(RMonitorReport):
    """RMONITOR Extra Info ($E)

    Additional Instance Variables:
    - extra_key     Extra data item key
    - extra_value   Extra data item value
    """
    def _setup(self):
        self.extra_key    = self.fields[1]
        self.extra_value  = self.fields[2]

@RMonitorReport.register('$F')
@RMonitorReport.single_key
class RMonitor_Flag(RMonitorReport):
    """RMONITOR Flag / Run State ($F)

    Additional Instance Variables:
    - laps_left     Laps remaining, or None
    - time_left     Time remaining, or None
    - tod           Time of day
    - elapsed       Elapsed time
    - flag          Flag condition
    """
    def _setup(self):
        self.laps_left  = int(self.fields[1])
        self.time_left  = self.fields[2]
        self.tod        = self.fields[3]
        self.elapsed    = self.fields[4]
        self.flag       = self.fields[5].strip()
        if self.laps_left == 9999:       self.laps_left = None
        if self.time_left == "00:00:00": self.time_left = None

@RMonitorReport.register('$G')
@RMonitorReport.int_key
class RMonitor_PositionData(RMonitorReport):
    """RMONITOR Race Position Report ($G)

    Additional Instance Variables:
    - pos           Position (integer)
    - id            Competitor ID
    - laps          Laps completed
    - time          Total time
    """
    def _setup(self):
        self.pos    = int(self.fields[1])
        self.id     = self.fields[2]
        self.laps   = 0 if self.fields[3] == '' else int(self.fields[3])
        self.time   = self.fields[4]

@RMonitorReport.register('$H')
@RMonitorReport.int_key
class RMonitor_LapTimeData(RMonitorReport):
    """RMONITOR Practice/Qualifying Report ($H)

    Additional Instance Variables:
    - pos           Position (integer)
    - id            Competitor ID
    - best_lap      Best lap, or None
    - best_time     Best lap time, or None
    """
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
    def cache_key(self):
        """Return a key used for caching this report, or None.

        This record type ($I) is a special case -- it contains global state,
        but also must be reported first, before any other cache data, because
        clients receiving this report will discard any previously-received
        information. To achieve this, the empty string is used as the key.
        """
        return ''
    def _setup(self):
        self.tod        = self.fields[1]
        self.date       = self.fields[2]

@RMonitorReport.register('$J')
@RMonitorReport.string_key
class RMonitor_PassingData(RMonitorReport):
    """RMONITOR Passing Report ($J)

    Additional Instance Variables:
    - id            Competitor ID
    - last_lap      Last lap time, or None
    - time          Total time
    """
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
@RMonitorReport.single_key
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
    def __init__(self, signal=None):
        """Create a new RMONITOR cache."""
        self.__cache = {}

    def process(self, report):
        if report.kind == '$I': self.__cache = {}
        key = report.cache_key()
        if key is not None:
            self.__cache[key] = report
