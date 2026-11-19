"""Persistent hysteresis for cooperating inference clients; no direct hardware control."""
import math
from pathlib import Path
import sqlite3
from .private_store import PrivateStore, StoreError
from .recovery import ResourceGuard, RecoveryError, thermal_reader

class _ThermalState(PrivateStore):
    name='thermal'
    def initialize(self):
        with self.db:
            self.db.execute('CREATE TABLE IF NOT EXISTS latch (id INTEGER PRIMARY KEY CHECK(id=1), sensor TEXT NOT NULL, high REAL NOT NULL, low REAL NOT NULL, blocked INTEGER NOT NULL CHECK(blocked IN (0,1)))')

class ThermalLatch:
    def __init__(self,state,sensor,reader,*,high=43.,low=39.5):
        if not isinstance(sensor,str) or not 0<len(sensor)<=1024 or type(high) not in (float,int) or type(low) not in (float,int) or not 20<=low<high<=100 or not callable(reader):
            raise RecoveryError('Invalid thermal hysteresis configuration')
        self.state,self.sensor,self.reader,self.high,self.low=state,sensor,reader,high,low

    def check(self):
        try:
            with _ThermalState(self.state) as store:
                row=store.db.execute('SELECT sensor,high,low,blocked FROM latch WHERE id=1').fetchone()
                if row and row[3] not in (0,1): raise RecoveryError('Invalid thermal latch')
                if row and row[3] and row[:3]!=(self.sensor,self.high,self.low): raise RecoveryError('Restore original thermal sensor/thresholds to clear hot latch')
                try:
                    temp=self.reader()
                    valid=type(temp) in (int,float) and math.isfinite(temp) and -20<=temp<=150
                except (OSError,ValueError,TypeError,OverflowError): valid=False; temp=None
                blocked=not valid or temp>=self.high or bool(row and row[3] and temp>self.low)
                with store.db:
                    store.db.execute('INSERT OR REPLACE INTO latch VALUES (1,?,?,?,?)',(self.sensor,self.high,self.low,int(blocked)))
            if blocked: raise RecoveryError('Thermal hysteresis blocks inference until safe recovery threshold')
        except (StoreError,sqlite3.Error,OSError): raise RecoveryError('Thermal state unavailable; inference denied') from None


def inference_guard(*,min_memory_mib,thermal_sensor=None,max_temperature=43.,resume_temperature=None,lease_dir=None):
    if resume_temperature is not None and not thermal_sensor: raise RecoveryError('Resume temperature requires sensor')
    if thermal_sensor is None:
        guard=ResourceGuard(min_memory_mib=min_memory_mib)
        def check_without_sensor():
            if lease_dir is not None:
                state=Path(lease_dir)/'thermal.sqlite3'
                if state.exists() or state.is_symlink():
                    # Do not bypass a previously configured latch by omitting flags.
                    raise RecoveryError('Shared lease has thermal state; specify the configured thermal sensor')
            guard.check()
        return check_without_sensor
    if lease_dir is None:
        if resume_temperature is not None: raise RecoveryError('Persistent hysteresis requires shared lease directory')
        return ResourceGuard(min_memory_mib=min_memory_mib,max_temperature=max_temperature,temperature_reader=thermal_reader(thermal_sensor)).check
    low=max_temperature-3.5 if resume_temperature is None else resume_temperature
    guard=ResourceGuard(min_memory_mib=min_memory_mib)
    latch=ThermalLatch(lease_dir,str(Path(thermal_sensor).absolute()),thermal_reader(thermal_sensor),high=max_temperature,low=low)
    def check():
        # Observe thermal transitions even when available RAM is too low.
        latch.check(); guard.check()
    return check
