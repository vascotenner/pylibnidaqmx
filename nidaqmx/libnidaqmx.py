#!/usr/bin/env python
"""
ctypes based wrapper to the NIDAQmx library
===========================================

Tested with NIDAQwx library 8.0 using PCI-6602 and PCIe-6259 cards.

Usage
-----

To create task handle, use

  Task(name="")

where Task is [Analog|Digital|Counter][Input|Output]Task,

Task methods:

  start()
  stop()
  is_done()
  alter_state(state=start|stop|verify|commit|reserve|unreserve|abort)
  wait_until_done(timeout=-1)

  register_every_n_samples_event(func,samples=1,options=0|sync,cb_data=None)
  register_done_event(func,options=,cb_data=)
  register_signal_event(func,signal=sample_clock|sample_complete|change_detection|counter_output,options=,cb_data)

  
  configure_timing_handchaking(sample_mode=,samples_per_channel=)
  configure_timing_implicit(sample_mode=,samples_per_channel=)
  configure_timing_change_detection(rising_edge_channel=,falling_edge_channel=,sample_mode=,samples_per_channel=)
  configure_timing_sample_clock(source=OnboardClock,rate=1,
    active_edge=rising|falling,sample_mode=finite|continuous|hwtimed,samples_per_channel=)
  
  configure_trigger_analog_edge_start(source, slope=rising|falling,level=)
  configure_trigger_analog_window_start(source, when=entering|leaving,top=,bottom=)
  configure_trigger_digital_edge_start(source, edge=rising|falling)
  configure_trigger_digital_pattern_start(source, pattern, when=matches|does_not_match)
  configure_trigger_disable_start()

  set_buffer(samples_per_channel)
  set/get/reset_buffer_size(sz//)
  set/get/reset_max(channel_name,value//)
  set/get/reset_min(channel_name,value//)
  get_low/high/gain/measurment_type/units/auto_zero_mode/data_transfer_mechanism(channel_name)

  set/get/reset_regeneration(bool//)

  set/get/reset_arm_start_trigger(trigger_type=digital_edge//)
  set_arm_start_trigger_source(source)
  set_arm_start_trigger_edge(edge=rising|falling)

  set_pause_trigger(trigger_type=analog_level|analog_window|digital_level)
  set_pause_trigger_source(source)
  set_pause_trigger_when(when=above|below|inside|outside|high|low)

AnalogInput/OutputTask methods:
  
  create_voltage_channel(phys_channel,channel_name=,terminal=default|rse|nrse|diff|pseudodiff,
    min_val=,max_val=,units=volts|custom,custom_scale_name=)

  read(samples_per_channel=,timeout=10,fill_mode=group_by_scan_number|group_by_channel) -> data
  write(data, auto_start=True,timeout=10,layout=group_by_scan_number|group_by_channel)

DigitalInput/OutputTask methods:

  create_channel(lines, name=, grouping=per_line|for_all_lines)

  read(samples_per_channel=,timeout=10,fill_mode=group_by_scan_number|group_by_channel) -> data, bytes_per_sample
  write(data,auto_start=True,timeout=10,layout=group_by_scan_number|group_by_channel)

CounterInput/OutputTask methods:

  create_channel_count_edges(counter,name=,edge=rising|falling,init=0,direction=up|down|ext)
  set_terminal_count_edges(channel, terminal)

  create_channel_frequency(counter,name=,units=hertz,idle_state=low|high,delay=0,freq=1,duty_cycle=0.5)
  create_channel_ticks(counter,name=,source=,idle_state=low|high,delay=0,low_ticks=1,high_ticks=1)
  create_channel_time(counter,name=,units=seconds,idle_state=low|high,delay=0,low_time=1,high_time=1)

  set_terminal_pulse(channel, terminal)

"""
# Author: Pearu Peterson
# Created: July 2009

__all__ = ['AnalogInputTask', 'AnalogOutputTask',
           'DigitalInputTask', 'DigitalOutputTask',
           'CounterInputTask', 'CounterOutputTask',
           ]

import os
import sys
import textwrap
import numpy as np
from numpy import ctypeslib
import ctypes
import ctypes.util

lib = ctypes.util.find_library('nidaqmx')

if lib is None:
    raise ImportError('Failed to find NI-DAQmx library. Make sure that libnidaqmx is installed and its location is listed in PATH|LD_LIBRARY_PATH|..')

libnidaqmx = ctypes.cdll.LoadLibrary(lib)

int8 = ctypes.c_int8
uInt8 = ctypes.c_uint8
int16 = ctypes.c_int16
uInt16 = ctypes.c_uint16
int32 = ctypes.c_int32
TaskHandle = bool32 = uInt32 = ctypes.c_uint32
int64 = ctypes.c_int64
uInt64 = ctypes.c_uint64

float32 = ctypes.c_float
float64 = ctypes.c_double
void_p = ctypes.c_void_p

def get_nidaqmx_version ():
    d = uInt32 (0)
    libnidaqmx.DAQmxGetSysNIDAQMajorVersion(ctypes.byref(d))
    major = d.value
    libnidaqmx.DAQmxGetSysNIDAQMinorVersion(ctypes.byref(d))
    minor = d.value
    return '%s.%s' % (major, minor)

nidaqmx_version = get_nidaqmx_version()
nidaqmx_h_name = 'nidaqmx_h_%s' % (nidaqmx_version.replace ('.', '_'))

try:
    exec 'import %s as nidaqmx_h' % (nidaqmx_h_name)
except ImportError:
    nidaqmx_h = None

if nidaqmx_h is None:
    # TODO: Find the location of the NIDAQmx.h automatically
    include_nidaqmx_h = '/usr/local/include/NIDAQmx.h'
    assert os.path.isfile (include_nidaqmx_h), `include_nidaqmx_h`    

    d = {}
    l = ['# This file is auto-generated. Do not edit!']
    error_map = {}
    f = open (include_nidaqmx_h, 'r')
    for line in f.readlines():
        if not line.startswith('#define'): continue
        i = line.find('//')
        words = line[7:i].strip().split(None, 2)
        if len (words)!=2: continue
        name, value = words
        if not name.startswith('DAQmx') or name.endswith(')'):
            continue
        if value.startswith('0x'):
            exec '%s = %s' % (name, value)
            d[name] = eval(value)
            l.append('%s = %s' % (name, value))
        elif name.startswith('DAQmxError') or name.startswith('DAQmxWarning'):
            assert value[0]=='(' and value[-1]==')', `name, value`
            value = int(value[1:-1])
            error_map[value] = name[10:]
        elif name.startswith('DAQmx_Val') or name[5:] in ['Success','_ReadWaitMode']:
            d[name] = eval(value)
            l.append('%s = %s' % (name, value))
        else:
            print name, value
            pass
    l.append('error_map = %r' % (error_map))

    fn = os.path.join (os.path.dirname(os.path.abspath (__file__)), nidaqmx_h_name+'.py')
    print 'Generating %r' % (fn)
    f = open(fn, 'w')
    f.write ('\n'.join(l) + '\n')
    f.close()
else:
    d = nidaqmx_h.__dict__

for name, value in d.items():
    if name.startswith ('_'): continue
    exec '%s = %r' % (name, value)

def CHK(return_code, funcname):
    if return_code==0: # call was succesful
        pass
    else:
        buf_size = 1000
        buf = ctypes.create_string_buffer('\000' * buf_size)
        r = libnidaqmx.DAQmxGetErrorString(return_code, ctypes.byref(buf), buf_size)
        if r:
            if return_code < 0:
                raise RuntimeError('%s failed with error %s=%d: %s'%\
                                       (funcname, error_map[return_code], return_code, repr(buf.value)))
            else:
                warning = error_map.get(return_code, return_code)
                sys.stderr.write('%s warning: %s\n' % (funcname, warning))                
        else:
            text = '\n  '.join(['']+textwrap.wrap(buf.value, 80)+['-'*10])
            if return_code < 0:
                raise RuntimeError('%s:%s' % (funcname, text))
            else:
                sys.stderr.write('%s warning:%s\n' % (funcname, text))
    return return_code

def CALL(name, *args):
    funcname = 'DAQmx' + name
    func = getattr(libnidaqmx, funcname)
    new_args = []
    for a in args:
        if isinstance (a, unicode):
            print name, 'argument',a, 'is unicode'
            new_args.append (str (a))
        else:
            new_args.append (a)
    r = func(*new_args)
    r = CHK(r, funcname)
    return r

def make_pattern(paths):
    """
    See _test_make_pattern
    """
    patterns = {}
    flag = False
    for path in paths:
        splitted = path.split('/',1)
        if len(splitted)==1:
            if patterns:
                assert flag,`flag,paths,patterns, path,splitted`
            flag = True
            word = splitted[0]
            i = 0
            while i<len(word):
                if word[i].isdigit():
                    break
                i += 1
            
            splitted = [word[:i], word[i:]]
        l = patterns.get(splitted[0], None)
        if l is None:
            l = patterns[splitted[0]] = set ([])
        map(l.add, splitted[1:])
    r = []
    for prefix in sorted(patterns.keys()):
        lst = list (patterns[prefix])
        if len (lst)==1:
            if flag:
                r.append(prefix + lst[0])
            else:
                r.append(prefix +'/'+ lst[0])
        elif lst:
            if prefix:
                subpattern = make_pattern (lst)
                if ',' in subpattern:
                    subpattern = '{%s}' % (subpattern)
                if flag:
                    r.append(prefix+subpattern)
                else:
                    r.append(prefix+'/'+subpattern)
            else:
                slst = sorted(map(int,lst))
                assert slst == range(slst[0], slst[-1]+1),`slst, lst`
                if len (slst)==1:
                    r.append(str (slst[0]))
                else:
                    r.append('%s:%s' % (slst[0],slst[-1]))
        else:
            r.append(prefix)
    return ','.join(r)


def _test_make_pattern():
    paths = ['Dev1/ao1', 'Dev1/ao2','Dev1/ao3', 'Dev1/ao4',
             'Dev1/ao5','Dev1/ao6','Dev1/ao7']
    assert make_pattern(paths)=='Dev1/ao1:7',`make_pattern(paths)`
    paths += ['Dev0/ao1']
    assert make_pattern(paths)=='Dev0/ao1,Dev1/ao1:7',`make_pattern(paths)`
    paths += ['Dev0/ao0']
    assert make_pattern(paths)=='Dev0/ao0:1,Dev1/ao1:7',`make_pattern(paths)`
    paths += ['Dev1/ai1', 'Dev1/ai2','Dev1/ai3']
    assert make_pattern(paths)=='Dev0/ao0:1,Dev1/{ai1:3,ao1:7}',`make_pattern(paths)`
    paths += ['Dev2/port0/line0']
    assert make_pattern(paths)=='Dev0/ao0:1,Dev1/{ai1:3,ao1:7},Dev2/port0/line0',`make_pattern(paths)`
    paths += ['Dev2/port0/line1']
    assert make_pattern(paths)=='Dev0/ao0:1,Dev1/{ai1:3,ao1:7},Dev2/port0/line0:1',`make_pattern(paths)`
    paths += ['Dev2/port1/line0','Dev2/port1/line1']
    assert make_pattern(paths)=='Dev0/ao0:1,Dev1/{ai1:3,ao1:7},Dev2/{port0/line0:1,port1/line0:1}',`make_pattern(paths)`

class Device(str):

    def get_product_type (self):
        """
        Indicates the product name of the device.
        """
        buf_size = 1000
        buf = ctypes.create_string_buffer('\000' * buf_size)
        CALL ('GetDevProductType', self, ctypes.byref (buf), buf_size)
        return buf.value

    def get_product_number (self):
        """
        Indicates the unique hardware identification number for the
        device.
        """
        d = uInt32 (0)
        CALL ('GetDevProductNum', self, ctypes.byref(d))
        return d.value

    def get_serial_number (self):
        """
        Indicates the serial number of the device. This value is zero
        if the device does not have a serial number.
        """
        d = uInt32 (0)
        CALL ('GetDevSerialNum', self, ctypes.byref(d))
        return d.value

    def get_analog_input_channels(self):
        """
        Indicates an array containing the names of the analog input
        physical channels available on the device.
        """
        buf_size = 1000
        buf = ctypes.create_string_buffer('\000' * buf_size)
        CALL ('GetDevAIPhysicalChans', self, ctypes.byref (buf), buf_size)
        names = [n.strip() for n in buf.value.split(',') if n.strip()]
        return names        

    def get_analog_output_channels(self):
        """
        Indicates an array containing the names of the analog output
        physical channels available on the device.
        """
        buf_size = 1000
        buf = ctypes.create_string_buffer('\000' * buf_size)
        CALL ('GetDevAOPhysicalChans', self, ctypes.byref (buf), buf_size)
        names = [n.strip() for n in buf.value.split(',') if n.strip()]
        return names        

    def get_digital_input_lines(self):
        """
        Indicates an array containing the names of the digital input
        lines available on the device.
        """
        buf_size = 1000
        buf = ctypes.create_string_buffer('\000' * buf_size)
        CALL ('GetDevDILines', self, ctypes.byref (buf), buf_size)
        names = [n.strip() for n in buf.value.split(',') if n.strip()]
        return names        

    def get_digital_input_ports(self):
        """
        Indicates an array containing the names of the digital input
        ports available on the device.
        """
        buf_size = 1000
        buf = ctypes.create_string_buffer('\000' * buf_size)
        CALL ('GetDevDIPorts', self, ctypes.byref (buf), buf_size)
        names = [n.strip() for n in buf.value.split(',') if n.strip()]
        return names        

    def get_digital_output_lines(self):
        """
        Indicates an array containing the names of the digital output
        lines available on the device.
        """
        buf_size = 1000
        buf = ctypes.create_string_buffer('\000' * buf_size)
        CALL ('GetDevDOLines', self, ctypes.byref (buf), buf_size)
        names = [n.strip() for n in buf.value.split(',') if n.strip()]
        return names        

    def get_digital_output_ports(self):
        """
        Indicates an array containing the names of the digital output
        ports available on the device.
        """
        buf_size = 1000
        buf = ctypes.create_string_buffer('\000' * buf_size)
        CALL ('GetDevDOPorts', self, ctypes.byref (buf), buf_size)
        names = [n.strip() for n in buf.value.split(',') if n.strip()]
        return names        

    def get_counter_input_channels (self):
        """
        Indicates an array containing the names of the counter input
        physical channels available on the device.
        """
        buf_size = 1000
        buf = ctypes.create_string_buffer('\000' * buf_size)
        CALL ('GetDevCIPhysicalChans', self, ctypes.byref (buf), buf_size)
        names = [n.strip() for n in buf.value.split(',') if n.strip()]
        return names        

    def get_counter_output_channels (self):
        """
        Indicates an array containing the names of the counter output
        physical channels available on the device.
        """
        buf_size = 1000
        buf = ctypes.create_string_buffer('\000' * buf_size)
        CALL ('GetDevCOPhysicalChans', self, ctypes.byref (buf), buf_size)
        names = [n.strip() for n in buf.value.split(',') if n.strip()]
        return names        

    def get_bus_type(self):
        """
        Indicates the bus type of the device.
        """
        bus_type_map = {DAQmx_Val_PCI: 'PCI',
                        DAQmx_Val_PCIe: 'PCIe',
                        DAQmx_Val_PXI: 'PXI',
                        DAQmx_Val_SCXI:'SCXI',
                        DAQmx_Val_PCCard:'PCCard',
                        DAQmx_Val_USB:'USB',
                        DAQmx_Val_Unknown:'UNKNOWN'}
        d = int32(0)
        CALL ('GetDevBusType', self, ctypes.byref (d))
        return bus_type_map[d.value]

    def get_pci_bus_number (self):
        """
        Indicates the PCI bus number of the device.
        """
        d = uInt32(0)
        CALL ('GetDevPCIBusNum', self, ctypes.byref (d))
        return d.value

    def get_pci_device_number (self):
        """
        Indicates the PCI slot number of the device.
        """
        d = uInt32(0)
        CALL ('GetDevPCIDevNum', self, ctypes.byref (d))
        return d.value

    def get_pxi_slot_number (self):
        """
        Indicates the PXI slot number of the device.
        """
        d = uInt32(0)
        CALL ('GetDevPXISlotNum', self, ctypes.byref (d))
        return d.value

    def get_pxi_chassis_number (self):
        """
        Indicates the PXI chassis number of the device, as identified
        in MAX.
        """
        d = uInt32(0)
        CALL ('GetDevPXIChassisNum', self, ctypes.byref (d))
        return d.value

    def get_bus(self):
        t = self.get_bus_type()
        if t in ['PCI', 'PCIe']:
            return '%s (bus=%s, device=%s)' % (t, self.get_pci_bus_number (), self.get_pci_device_number())
        if t=='PXI':
            return '%s (chassis=%s, slot=%s)' % (t, self.get_pxi_chassis_number (), self.get_pxi_slot_number())
        return t

class Task(uInt32):

    @classmethod
    def get_major_version(cls):
        d = uInt32 (0)
        CALL ('GetSysNIDAQMajorVersion', ctypes.byref (d))
        return d.value

    @classmethod
    def get_minor_version(cls):
        d = uInt32 (0)
        CALL ('GetSysNIDAQMinorVersion', ctypes.byref (d))
        return d.value

    @classmethod
    def get_version (cls):
        return '%s.%s' % (cls.get_major_version (), cls.get_minor_version ())

    @classmethod
    def get_system_devices(cls):
        """
        Indicates the names of all devices installed in the system.
        """
        buf_size = 1000
        buf = ctypes.create_string_buffer('\000' * buf_size)
        CALL ('GetSysDevNames', ctypes.byref (buf), buf_size)
        names = [Device(n.strip()) for n in buf.value.split(',') if n.strip()]
        return names

    @classmethod
    def get_system_tasks(cls):
        """
        Indicates an array that contains the names of all tasks saved
        on the system.
        """
        buf_size = 1000
        buf = ctypes.create_string_buffer('\000' * buf_size)
        CALL ('GetSysTasks', ctypes.byref (buf), buf_size)
        names = [n.strip() for n in buf.value.split(',') if n.strip()]
        return names

    @classmethod
    def get_system_global_channels(cls):
        """
        Indicates an array that contains the names of all global
        channels saved on the system.
        """
        buf_size = 1000
        buf = ctypes.create_string_buffer('\000' * buf_size)
        CALL ('GetSysGlobalChans', ctypes.byref (buf), buf_size)
        names = [n.strip() for n in buf.value.split(',') if n.strip()]
        return names

    channel_type = None # AI, AO, DI, DO, CI, CO

    def __init__(self, name = ""):
        """
        Creates a task.

        If you create a task within a loop, NI-DAQmx creates a new
        task in each iteration of the loop. Use `del task` within the
        loop after you finish with the task to avoid allocating
        unnecessary memory.
        """
        name = str(name)
        uInt32.__init__(self, 0)
        CALL('CreateTask', name, ctypes.byref(self))
        buf_size = 1000
        buf = ctypes.create_string_buffer('\000' * buf_size)
        r = CALL('GetTaskName', self, ctypes.byref(buf), buf_size)
        self.name = buf.value
        self.sample_mode = None

    def set_channel_type(self, t):
        assert t in ['AI', 'AO', 'DI', 'DO', 'CI', 'CO'],`t`
        if self.channel_type is None:
            self.channel_type = t
        elif self.channel_type != t:
            raise ValueError('Expected channel type %r but got %r' % (self.channel_type, t))

    @property
    def channel_io_type (self):
        t = self.channel_type
        if t is None:
            raise TypeError('%s: cannot determine channel I/O type when no channels have been created.' % (self.__class__.__name__))
        return 'input' if t[1]=='I' else 'output'

    def __del__ (self, libnidaqmx=libnidaqmx):
        """
        Clears the task.

        Before clearing, this function stops the task, if necessary,
        and releases any resources reserved by the task. You cannot
        use a task once you clear the task without recreating or
        reloading the task.

        If you use the DAQmxCreateTask function or any of the NI-DAQmx
        Create Channel functions within a loop, use this function
        within the loop after you finish with the task to avoid
        allocating unnecessary memory.
        """
        if self.value:
            r = libnidaqmx.DAQmxClearTask(self)
            if r:
                print "DAQmxClearTask failed with error code %s" % (r)


    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.name)

    def is_done(self):
        """
        Queries the status of the task and indicates if it completed
        execution. Use this function to ensure that the specified
        operation is complete before you stop the task.
        """
        b = bool32(0)
        if not CALL('IsTaskDone', self, ctypes.byref(b)):
            return b != 0

    # NotImplemented: DAQmxGetTaskComplete

    def start(self):
        """
        Transitions the task from the committed state to the running
        state, which begins measurement or generation. Using this
        function is required for some applications and optional for
        others.

        If you do not use this function, a measurement task starts
        automatically when a read operation begins. The autoStart
        parameter of the NI-DAQmx Write functions determines if a
        generation task starts automatically when you use an NI-DAQmx
        Write function.

        If you do not call StartTask and StopTask when you
        call NI-DAQmx Read functions or NI-DAQmx Write functions
        multiple times, such as in a loop, the task starts and stops
        repeatedly. Starting and stopping a task repeatedly reduces
        the performance of the application.

        Returns True on success.
        """
        return CALL('StartTask', self) == 0

    def stop (self):
        """
        Stops the task and returns it to the state it was in before
        you called StartTask or called an NI-DAQmx Write function with
        autoStart set to TRUE.

        If you do not call StartTask and StopTask when you call
        NI-DAQmx Read functions or NI-DAQmx Write functions multiple
        times, such as in a loop, the task starts and stops
        repeatedly. Starting and stopping a task repeatedly reduces
        the performance of the application.

        Returns True on success.
        """
        return CALL('StopTask', self) == 0

    @classmethod
    def _get_map_value(cls, label, map, key):
        val = map.get(key)
        if val is None:
            raise ValueError('Expected %s %s but got %r' % (label, '|'.join(map.keys ()), key))
        return val

    def get_number_of_channels(self):
        """
        Indicates the number of virtual channels in the task.
        """
        d = uInt32(0)
        CALL('GetTaskNumChans', self, ctypes.byref(d))
        return d.value
        
    def get_names_of_channels (self):
        buf_size = 1000
        buf = ctypes.create_string_buffer('\000' * buf_size)
        CALL('GetTaskChannels', self, ctypes.byref(buf), buf_size)
        names = [n.strip() for n in buf.value.split(',') if n.strip()]
        n = self.get_number_of_channels()
        assert len(names)==n,`names, n`
        return names

    def get_devices (self):
        buf_size = 1000
        buf = ctypes.create_string_buffer('\000' * buf_size)
        CALL('GetTaskDevices', self, ctypes.byref(buf), buf_size)
        names = [n.strip() for n in buf.value.split(',') if n.strip()]
        return names

    def alter_state(self, state):
        """
        Alters the state of a task according to the action you
        specify. To minimize the time required to start a task, for
        example, DAQmxTaskControl can commit the task prior to
        starting.

        Actions:

        'start' - Starts execution of the task.

        'stop' - Stops execution of the task.

        'verify' - Verifies that all task parameters are valid for the
          hardware.

        'commit' - Programs the hardware as much as possible according
          to the task configuration.

        'reserve' - Reserves the hardware resources needed for the
          task. No other tasks can reserve these same resources.

        'unreserve' - Releases all previously reserved resources.

        'abort' - Abort is used to stop an operation, such as Read or
          Write, that is currently active. Abort puts the task into an
          unstable but recoverable state. To recover the task, call
          Start to restart the task or call Stop to reset the task
          without starting it.

        Returns True on success.
        """
        state_map = dict(start = DAQmx_Val_Task_Start,
                         stop = DAQmx_Val_Task_Stop,
                         verify = DAQmx_Val_Task_Verify,
                         commit = DAQmx_Val_Task_Commit,
                         reserve = DAQmx_Val_Task_Reserve,
                         unreserve = DAQmx_Val_Task_Unreserve,
                         abort = DAQmx_Val_Task_Abort)
        state_val = self._get_map_value ('state', state_map, state)
        return CALL('TaskControl', self, state_val) == 0

    # Not implemented: DAQmxAddGlobalChansToTask, DAQmxLoadTask
    # DAQmxGetNthTaskChannel

    _register_every_n_samples_event_cache = None

    def register_every_n_samples_event(self, func, 
                                       samples = 1,
                                       options = 0,
                                       cb_data = None
                                       ):
        """
        Registers a callback function to receive an event when the
        specified number of samples is written from the device to the
        buffer or from the buffer to the device. This function only
        works with devices that support buffered tasks.

        When you stop a task explicitly any pending events are
        discarded. For example, if you call DAQmxStopTask then you do
        not receive any pending events.

        Parameters:

        func - The function that you want DAQmx to call when the event
          occurs. The function you pass in this parameter must have
          the following prototype:

          def func(task, event_type, samples, cb_data):
              return 0

          Upon entry to the callback, the task parameter contains the
          handle to the task on which the event occurred. The
          event_type parameter contains the value you passed in the
          event_type parameter of this function. The samples parameter
          contains the value you passed in the samples parameter of
          this function. The cb_data parameter contains the value you
          passed in the cb_data parameter of this function.

        samples - The number of samples after which each event should
          occur.

        options, cb_data - see register_done_event documentation.
        """
        event_type_map = dict(input=DAQmx_Val_Acquired_Into_Buffer, 
                              output=DAQmx_Val_Transferred_From_Buffer)
        event_type = event_type_map[self.channel_io_type]

        if options=='sync':
            options = DAQmx_Val_SynchronousEventCallbacks

        if func is None:
            c_func = None # to unregister func
        else:
            if self._register_every_n_samples_event_cache is not None:
                # unregister:
                self.register_every_n_samples_event(None, samples=samples, options=options, cb_data=cb_data)
            # TODO: check the validity of func signature
            # TODO: use wrapper function that converts cb_data argument to given Python object
            c_func = EveryNSamplesEventCallback_map[self.channel_type](func)
        
        self._register_every_n_samples_event_cache = c_func

        return CALL('RegisterEveryNSamplesEvent', self, event_type, uInt32(samples), uInt32 (options), c_func, cb_data)==0

    _register_done_event_cache = None

    def register_done_event(self, func, options = 0, cb_data = None):
        """
        Registers a callback function to receive an event when a task
        stops due to an error or when a finite acquisition task or
        finite generation task completes execution. A Done event does
        not occur when a task is stopped explicitly, such as by
        calling DAQmxStopTask.

        Parameters:

        func - The function that you want DAQmx to call when the event
          occurs.  The function you pass in this parameter must have
          the following prototype:

          def func(task, status, cb_data = None):
              return 0

          Upon entry to the callback, the taskHandle parameter
          contains the handle to the task on which the event
          occurred. The status parameter contains the status of the
          task when the event occurred. If the status value is
          negative, it indicates an error. If the status value is
          zero, it indicates no error. If the status value is
          positive, it indicates a warning. The callbackData parameter
          contains the value you passed in the callbackData parameter
          of this function.

        options - Use this parameter to set certain options. You can
          combine flags with the bitwise-OR operator ('|') to set
          multiple options. Pass a value of zero if no options need to
          be set.
          
          'sync' - The callback function is called in the thread which
            registered the event. In order for the callback to occur,
            you must be processing messages. If you do not set this
            flag, the callback function is called in a DAQmx thread by
            default.
            
          Note: If you are receiving synchronous events faster than
          you are processing them, then the user interface of your
          application might become unresponsive.

        cb_data - A value that you want DAQmx to pass to the callback
          function as the function data parameter. Do not pass the
          address of a local variable or any other variable that might
          not be valid when the function is executed.
        """
        if options=='sync':
            options = DAQmx_Val_SynchronousEventCallbacks

        if func is None:
            c_func = None
        else:
            if self._register_done_event_cache is not None:
                self.register_done_event(None, options=options, cb_data=cb_data)
            # TODO: check the validity of func signature
            c_func = DoneEventCallback_map[self.channel_type](func)
        self._register_done_event_cache = c_func

        return CALL('RegisterDoneEvent', self, uInt32 (options), c_func, cb_data)==0
   
    _register_signal_event_cache = None

    def register_signal_event(self, func, signal, options=0, cb_data = None):
        """
        Registers a callback function to receive an event when the
        specified hardware event occurs.

        When you stop a task explicitly any pending events are
        discarded. For example, if you call DAQmxStopTask then you do
        not receive any pending events.

        Parameters:

        func - The function that you want DAQmx to call when the event
          occurs. The function you pass in this parameter must have the
          following prototype:

          def func(task, signalID, cb_data):
            return 0

          Upon entry to the callback, the task parameter contains the
          handle to the task on which the event occurred. The signalID
          parameter contains the value you passed in the signal
          parameter of this function. The cb_data parameter contains
          the value you passed in the cb_data parameter of this
          function.

        signal - The signal for which you want to receive results:
        
          'sample_clock' - Sample clock
          'sample_complete' - Sample complete event
          'change_detection' - Change detection event
          'counter_output' - Counter output event

        options, cb_data - see register_done_event documentation.        
        """
        signalID_map = dict (
            sample_clock = DAQmx_Val_SampleClock,
            sample_complete = DAQmx_Val_SampleCompleteEvent,
            change_detection = DAQmx_Val_ChangeDetectionEvent,
            counter_output = DAQmx_Val_CounterOutputEvent
            )
        signalID_val = self._get_map_value('signalID', signalID_map, signal)
        if options=='sync':
            options = DAQmx_Val_SynchronousEventCallbacks

        if func is None:
            c_func = None
        else:
            if self._register_signal_event_cache is not None:
                self._register_signal_event(None, signal=signal, options=options, cb_data=cb_data)
            # TODO: check the validity of func signature
            c_func = SignalEventCallback_map[self.channel_type](func)
        self._register_signal_event_cache = c_func
        return CALL('RegisterSignalEvent', self, signalID_val, uInt32(options), c_func, cb_data)==0

    # Not implemented:
    # DAQmxCreateAIAccelChan, DAQmxCreateAICurrentChan, DAQmxCreateAIFreqVoltageChan,
    # DAQmxCreateAIMicrophoneChan, DAQmxCreateAIResistanceChan, DAQmxCreateAIRTDChan,
    # DAQmxCreateAIStrainGageChan, DAQmxCreateAITempBuiltInSensorChan,
    # DAQmxCreateAIThrmcplChan, DAQmxCreateAIThrmstrChanIex, DAQmxCreateAIThrmstrChanVex,
    # DAQmxCreateAIVoltageChanWithExcit
    # DAQmxCreateAIPosLVDTChan, DAQmxCreateAIPosRVDTChan

    # DAQmxCreateTEDSAI*



    # Not implemented: DAQmxCreateAOCurrentChan
    # DAQmxCreateDIChan, DAQmxCreateDOChan
    # DAQmxCreateCI*, DAQmxCreateCO*

    def configure_timing_change_detection(self,
                                          rising_edge_channel = '',
                                          falling_edge_channel = '',
                                          sample_mode = 'continuous', 
                                          samples_per_channel = 1000):
        """
        Configures the task to acquire samples on the rising and/or
        falling edges of the lines or ports you specify.
        """
        sample_mode_map = dict (finite = DAQmx_Val_FiniteSamps,
                                continuous = DAQmx_Val_ContSamps,
                                hwtimed = DAQmx_Val_HWTimedSinglePoint)
        sample_mode_val = self._get_map_value('sample_mode', sample_mode_map, sample_mode)
        self.samples_per_channel = samples_per_channel
        self.sample_mode = sample_mode
        r = CALL('CfgChangeDetectionTiming', self, rising_edge_channel, falling_edge_channel,
                 sample_mode_val, uInt64(samples_per_channel))
        return r==0


    def configure_timing_handshaking(self,
                                     sample_mode = 'continuous', 
                                     samples_per_channel = 1000):
        """
        Determines the number of digital samples to acquire or
        generate using digital handshaking between the device and a
        peripheral device.
        """
        sample_mode_map = dict (finite = DAQmx_Val_FiniteSamps,
                                continuous = DAQmx_Val_ContSamps,
                                hwtimed = DAQmx_Val_HWTimedSinglePoint)
        sample_mode_val = self._get_map_value('sample_mode', sample_mode_map, sample_mode)
        self.samples_per_channel = samples_per_channel
        self.sample_mode = sample_mode
        r = CALL('CfgHandshakingTiming', self, sample_mode_val, uInt64(samples_per_channel))
        return r==0

    def configure_timing_implicit(self,
                                  sample_mode = 'continuous', 
                                  samples_per_channel = 1000):
        """
        Sets only the number of samples to acquire or generate without
        specifying timing. Typically, you should use this function
        when the task does not require sample timing, such as tasks
        that use counters for buffered frequency measurement, buffered
        period measurement, or pulse train generation.
        """
        sample_mode_map = dict (finite = DAQmx_Val_FiniteSamps,
                                continuous = DAQmx_Val_ContSamps,
                                hwtimed = DAQmx_Val_HWTimedSinglePoint)
        sample_mode_val = self._get_map_value('sample_mode', sample_mode_map, sample_mode)
        self.samples_per_channel = samples_per_channel
        self.sample_mode = sample_mode
        r = CALL('CfgImplicitTiming', self, sample_mode_val, uInt64(samples_per_channel))
        return r==0

    def configure_timing_sample_clock(self, 
                                      source = 'OnboardClock', 
                                      rate = 1, # Hz
                                      active_edge = 'rising', 
                                      sample_mode = 'continuous', 
                                      samples_per_channel = 1000):
        """
        Sets the source of the Sample Clock, the rate of the Sample
        Clock, and the number of samples to acquire or generate.

        Parameters:

          source - The source terminal of the Sample Clock. To use the
            internal clock of the device, use None or use 'OnboardClock'.

          rate - The sampling rate in samples per second. If you use
            an external source for the Sample Clock, set this value to
            the maximum expected rate of that clock.

          active_edge - Specifies on which edge of the clock to
            acquire or generate samples:

            'rising' - Acquire or generate samples on the rising edges
              of the Sample Clock.

            'falling' - Acquire or generate samples on the falling
              edges of the Sample Clock.
  
          sample_mode - Specifies whether the task acquires or
            generates samples continuously or if it acquires or
            generates a finite number of samples:
            
            'finite' - Acquire or generate a finite number of samples.
            
            'continuous' - Acquire or generate samples until you stop the task.

            'hwtimed' - Acquire or generate samples continuously using
              hardware timing without a buffer. Hardware timed single
              point sample mode is supported only for the sample clock
              and change detection timing types.

          samples_per_channel - The number of samples to acquire or
            generate for each channel in the task if sample_mode is
            'finite'.  If sample_mode is 'continuous', NI-DAQmx uses
            this value to determine the buffer size.
        """
        source = str(source)
        active_edge_map = dict (rising = DAQmx_Val_Rising,
                                falling = DAQmx_Val_Falling)
        sample_mode_map = dict (finite = DAQmx_Val_FiniteSamps,
                                continuous = DAQmx_Val_ContSamps,
                                hwtimed = DAQmx_Val_HWTimedSinglePoint)
        active_edge_val = self._get_map_value('active_edge', active_edge_map, active_edge)
        sample_mode_val = self._get_map_value('sample_mode', sample_mode_map, sample_mode)
        self.samples_per_channel = samples_per_channel
        self.sample_mode = sample_mode
        r = CALL('CfgSampClkTiming', self, source, float64(rate), active_edge_val, sample_mode_val, 
                    uInt64(samples_per_channel))
        return r==0

    def configure_timing_burst_handshaking_export_clock(self, *args, **kws): 
        """
        Configures when the DAQ device transfers data to a peripheral
        device, using the DAQ device's onboard sample clock to control
        burst handshaking timing.
        """
        raise NotImplementedError

    def configure_timing_burst_handshaking_import_clock(self, *args, **kws): 
        """
        Configures when the DAQ device transfers data to a peripheral
        device, using an imported sample clock to control burst
        handshaking timing.
        """
        raise NotImplementedError

    def configure_trigger_analog_edge_start(self, source, slope='rising',level=1.0):
        """
        Configures the task to start acquiring or generating samples
        when an analog signal crosses the level you specify.

        Parameters:

        source - The name of a channel or terminal where there is an
          analog signal to use as the source of the trigger. For E
          Series devices, if you use a channel name, the channel must
          be the first channel in the task. The only terminal you can
          use for E Series devices is PFI0.

        slope - Specifies on which slope of the signal to start
          acquiring or generating samples when the signal crosses
          trigger level:

          'rising' - Trigger on the rising slope of the signal.
          'falling' - Trigger on the falling slope of the signal.

        level - The threshold at which to start acquiring or
          generating samples. Specify this value in the units of the
          measurement or generation. Use trigger slope to specify on
          which slope to trigger at this threshold.
        """
        slope_map = dict (rising=DAQmx_Val_RisingSlope,
                          falling=DAQmx_Val_FallingSlope)
        slope_val = self._get_map_value('slope', slope_map, slope)
        return CALL ('CfgAnlgEdgeStartTrig', self, source, slope_val, float64(level))==0

    def configure_trigger_analog_window_start(self, source, when='entering',top=1.0,bottom=-1.0):
        """
        Configures the task to start acquiring or generating samples
        when an analog signal enters or leaves a range you specify.

        Parameters:

        source - The name of a virtual channel or terminal where there
          is an analog signal to use as the source of the trigger.

          For E Series devices, if you use a virtual channel, it must
          be the first channel in the task. The only terminal you can
          use for E Series devices is PFI0.

        when - Specifies whether the task starts measuring or
          generating samples when the signal enters the window or when
          it leaves the window. Use windowBottom and windowTop to
          specify the limits of the window.

          'entering' - Trigger when the signal enters the window.
          'leaving' - Trigger when the signal leaves the window.

        top - The upper limit of the window. Specify this value in the
          units of the measurement or generation.

        bottom - The lower limit of the window. Specify this value in
          the units of the measurement or generation.
        """
        source = str(source)
        when_map = dict (entering=DAQmx_Val_EnteringWin,
                         leaving=DAQmx_Val_LeavingWin)
        when_val = self._get_map_value('when', when_map, when)
        return CALL ('CfgAnlgWindowStartTrig', self, source, when_val, float64(top), float64(bottom))==0

    def configure_trigger_digital_edge_start(self, source, edge='rising'):
        """
        Configures the task to start acquiring or generating samples
        on a rising or falling edge of a digital signal.

        Parameters:

        source - The name of a terminal where there is a digital
          signal to use as the source of the trigger.

        edge - Specifies on which edge of a digital signal to start
          acquiring or generating samples:

          'rising' - Rising edge(s).
          'falling' - Falling edge(s).

        """
        source = str(source)
        edge_map = dict (rising=DAQmx_Val_Rising,
                         falling=DAQmx_Val_Falling)
        edge_val = self._get_map_value ('edge', edge_map, edge)
        return CALL('CfgDigEdgeStartTrig', self, source, edge_val)

    def configure_trigger_digital_pattern_start(self, source, pattern, when='matches'):
        """
        Configures a task to start acquiring or generating samples
        when a digital pattern is matched.

        Parameters:

        source - Specifies the physical channels to use for pattern
          matching. The order of the physical channels determines the
          order of the pattern. If a port is included, the order of
          the physical channels within the port is in ascending order.

        pattern - Specifies the digital pattern that must be met for
          the trigger to occur.

        when - Specifies the conditions under which the trigger
          occurs:

          'matches' - Pattern matches.
          'does_not_match' - Pattern does not match.
        """
        source = str(source)
        pattern = str(pattern)
        when_map = dict(matches = DAQmx_Val_PatternMatches,
                        does_not_match = DAQmx_Val_PatternDoesNotMatch)
        when_val = self._get_map_value('when', when_map, when)
        return CALL('CfgDigPatternStartTrig', self, source, pattern, when_val)

    def configure_trigger_disable_start(self):
        """
        Configures the task to start acquiring or generating samples
        immediately upon starting the task.
        """
        return CALL ('DisableStartTrig', self)

    def set_buffer (self, samples_per_channel):
        """
        Overrides the automatic I/O buffer allocation that NI-DAQmx performs.

        Parameters:

        samples_per_channel - The number of samples the buffer can
          hold for each channel in the task. Zero indicates no buffer
          should be allocated. Use a buffer size of 0 to perform a
          hardware-timed operation without using a buffer.
        """
        channel_io_type = self.channel_io_type
        return CALL('Cfg%sBuffer' % (channel_io_type.title()), self, uInt32(samples_per_channel)) == 0



    # Not implemented:
    # DAQmxReadAnalogScalarF64
    # DAQmxReadBinary*, DAQmxReadCounter*, DAQmxReadDigital*
    # DAQmxGetNthTaskReadChannel, DAQmxReadRaw
    # DAQmxWrite*
    # DAQmxExportSignal
    # DAQmxCalculateReversePolyCoeff, DAQmxCreateLinScale
    # DAQmxWaitForNextSampleClock, DAQmxWaitUntilTaskDone
    # DAQmxSwitch*
    # DAQmxConnectTerms, DAQmxDisconnectTerms, DAQmxTristateOutputTerm
    # DAQmxResetDevice
    # DAQmxControlWatchdog*

    # DAQmxAOSeriesCalAdjust, DAQmxESeriesCalAdjust, DAQmxGet*,
    # DAQmxMSeriesCalAdjust, DAQmxPerformBridgeOffsetNullingCal, DAQmxRestoreLastExtCalConst
    # DAQmxSelfCal, DAQmxSetAIChanCalCalDate, DAQmxSetAIChanCalExpDate, DAQmxSSeriesCalAdjust
    # External Calibration, DSA Calibration, PXI-42xx Calibration, SCXI Calibration
    # Storage, TEDS
    # DAQmxSetAnalogPowerUpStates, DAQmxSetDigitalPowerUpStates
    # DAQmxGetExtendedErrorInfo

    def get_physical_channel_name(self, channel_name):
        """
        Indicates the name of the physical channel upon which this
        virtual channel is based.
        """
        channel_name = str (channel_name)
        buf_size = 1000
        buf = ctypes.create_string_buffer('\000' * buf_size)
        r = CALL('GetPhysicalChanName', self, channel_name, ctypes.byref(buf), uInt32(buf_size))
        return buf.value

    def get_channel_type(self, channel_name):
        """
        Indicates the type of the virtual channel.
        """
        channel_name = str (channel_name)
        t = int32(0)
        CALL('GetChanType', self, channel_name, ctypes.byref(t))
        channel_type_map = {DAQmx_Val_AI:'AI', DAQmx_Val_AO:'AO',
                            DAQmx_Val_DI:'DI', DAQmx_Val_DO:'DO',
                            DAQmx_Val_CI:'CI', DAQmx_Val_CO:'CO',
                            }
        return channel_type_map[t.value]

    def is_channel_global (self, channel_name):
        """
        Indicates whether the channel is a global channel.
        """
        channel_name = str (channel_name)
        d = bool32(0)
        CALL('GetChanIsGlobal', self, channel_name, ctypes.byref (d))
        return bool(d.value)

    # NotImplemented: DAQmx*ChanDescr

    def get_buffer_size (self, on_board=False):
        """
        Specifies the number of samples the I/O buffer can hold for
        each channel in the task. Zero indicates to allocate no
        buffer. Use a buffer size of 0 to perform a hardware-timed
        operation without using a buffer. Setting this property
        overrides the automatic I/O buffer allocation that NI-DAQmx
        performs.

        If on_board is True then specifies in samples per channel the
        size of the onboard I/O buffer of the device.
        """
        d = uInt32(0)
        channel_io_type = self.channel_io_type
        if on_board:
            CALL('GetBuf%sOnbrdBufSize' % (channel_io_type.title()), self, ctypes.byref(d))
        else:
            CALL('GetBuf%sBufSize' % (channel_io_type.title ()), self, ctypes.byref(d))
        return d.value

    def set_buffer_size(self, sz):
        channel_io_type = self.channel_io_type
        return CALL('SetBuf%sBufSize' % (channel_io_type.title()), self, uInt32 (sz)) == 0

    def reset_buffer_size(self):
        channel_io_type = self.channel_io_type
        return CALL('ResetBuf%sBufSize' % (channel_io_type.title()), self) == 0

    def get_max(self, channel_name):
        """
        Specifies the maximum value you expect to measure or generate.
        """
        channel_name = str(channel_name)
        d = float64(0)
        channel_type = self.channel_type
        CALL ('Get%sMax' % (channel_type), self, channel_name, ctypes.byref(d))
        return d.value

    def set_max(self, channel_name, value):
        channel_name = str(channel_name)
        channel_type = self.channel_type
        return CALL ('Set%sMax' % (channel_type), self, channel_name, float64 (value))==0

    def reset_max(self, channel_name):
        channel_name = str(channel_name)
        channel_type = self.channel_type
        return CALL ('Reset%sMax' % (channel_type), self, channel_name)==0

    def get_min(self, channel_name):
        """
        Specifies the minimum value you expect to measure or generate.
        """
        channel_name = str(channel_name)
        d = float64(0)
        channel_type = self.channel_type
        CALL ('Get%sMin' % (channel_type), self, channel_name, ctypes.byref(d))
        return d.value

    def set_min(self, channel_name, value):
        channel_name = str(channel_name)
        channel_type = self.channel_type
        return CALL ('Set%sMin' % (channel_type), self, channel_name, float64 (value))==0

    def reset_min(self, channel_name):
        channel_name = str(channel_name)
        channel_type = self.channel_type
        return CALL ('Reset%sMin' % (channel_type), self, channel_name)==0

    def get_high(self, channel_name):
        channel_name = str(channel_name)
        d = float64(0)
        channel_type = self.channel_type
        CALL ('Get%sRngHigh' % (channel_type), self, channel_name, ctypes.byref(d))
        return d.value

    def get_low(self, channel_name):
        channel_name = str(channel_name)
        d = float64(0)
        channel_type = self.channel_type
        CALL ('Get%sRngLow' % (channel_type), self, channel_name, ctypes.byref(d))
        return d.value

    def get_gain (self, channel_name):
        channel_name = str(channel_name)
        d = float64(0)
        channel_type = self.channel_type
        CALL ('Get%sGain' % (channel_type), self, channel_name, ctypes.byref(d))
        return d.value

    def get_measurment_type(self, channel_name):
        channel_name = str(channel_name)
        d = int32(0)
        channel_type = self.channel_type
        if channel_type=='AI':
            r = CALL('GetAIMeasType', self, channel_name, ctypes.byref (d))
        elif channel_type=='AO':
            r = CALL('GetAOOutputType', self, channel_name, ctypes.byref (d))
        else:
            raise NotImplementedError(`channel_name, channel_type`)
        measurment_type_map = {DAQmx_Val_Voltage:'voltage',
                               DAQmx_Val_Current:'current',
                               DAQmx_Val_Voltage_CustomWithExcitation:'voltage_with_excitation',
                               DAQmx_Val_Freq_Voltage:'freq_voltage',
                               DAQmx_Val_Resistance:'resistance',
                               DAQmx_Val_Temp_TC:'temperature',
                               DAQmx_Val_Temp_Thrmstr:'temperature',
                               DAQmx_Val_Temp_RTD:'temperature',
                               DAQmx_Val_Temp_BuiltInSensor:'temperature',
                               DAQmx_Val_Strain_Gage:'strain',
                               DAQmx_Val_Position_LVDT:'position_lvdt',
                               DAQmx_Val_Position_RVDT:'position_rvdt',
                               DAQmx_Val_Accelerometer:'accelration',
                               DAQmx_Val_SoundPressure_Microphone:'pressure',
                               DAQmx_Val_TEDS_Sensor:'TEDS'
                               }
        return measurment_type_map[d.value]

    def get_units (self, channel_name):
        channel_name = str(channel_name)
        mt = self.get_measurment_type(channel_name)
        channel_type = self.channel_type
        if mt=='voltage':
            d = int32(0)
            CALL('Get%sVoltageUnits' % (channel_type), self, channel_name, ctypes.byref(d))
            units_map = {DAQmx_Val_Volts:'volts',
                         #DAQmx_Val_FromCustomScale:'custom_scale',
                         #DAQmx_Val_FromTEDS:'teds',
                         }
            return units_map[d.value]
        raise NotImplementedError(`channel_name, mt`)

    def get_auto_zero_mode (self, channel_name):
        channel_name = str(channel_name)
        d = int32(0)
        channel_type = self.channel_type
        r = CALL('Get%sAutoZeroMode' % (channel_type), self, channel_name, ctypes.byref (d))
        auto_zero_mode_map = {DAQmx_Val_None:'none',
                              DAQmx_Val_Once:'once',
                              DAQmx_Val_EverySample:'every_sample'}
        return auto_zero_mode_map[d.value]

    def get_data_transfer_mechanism(self, channel_name):
        channel_name = str(channel_name)
        d = int32(0)
        channel_type = self.channel_type
        r = CALL('Get%sDataXferMech' % (channel_type), self, channel_name, ctypes.byref (d))
        data_transfer_mechanism_map = {DAQmx_Val_DMA:'dma',
                                       DAQmx_Val_Interrupts:'interrupts',
                                       DAQmx_Val_ProgrammedIO:'programmed_io',
                                       DAQmx_Val_USBbulk:'usb'}
        return data_transfer_mechanism_map[d.value]

    def get_regeneration(self):
        """
        Return True if regeneration (generating the same data more
        than once) is allowed.
        """
        d = int32(0)
        CALL('GetWriteRegenMode', self, ctypes.byref (d))
        if d.value==DAQmx_Val_AllowRegen:
            return True
        if d.value==DAQmx_Val_DoNotAllowRegen:
            return False
        assert 0,`d.value`

    def set_regeneration(self, allow = True):
        if allow:
            return CALL('SetWriteRegenMode', self, DAQmx_Val_AllowRegen)==0
        return CALL('SetWriteRegenMode', self, DAQmx_Val_DoNotAllowRegen)==0

    def reset_regeneration(self):
        return CALL('ResetWriteRegenMode', self)==0

    def set_arm_start_trigger(self, trigger_type='digital_edge'):
        """
        Specifies the type of trigger to use to arm the task for a
        Start Trigger. If you configure an Arm Start Trigger, the task
        does not respond to a Start Trigger until the device receives
        the Arm Start Trigger.

        Parameters:

        trigger_type:
        
          'digital_edge' - Trigger on a rising or falling edge of a digital signal.
          None - Disable the trigger.
        """
        if trigger_type=='digital_edge':
            trigger_type_val = DAQmx_Val_DigEdge
        elif trigger_type in ['disable', None]:
            trigger_type_val = DAQmx_Val_None
        else:
            assert 0,`trigger_type`
        return CALL('SetArmStartTrigType', self, trigger_type_val)==0

    def get_arm_start_trigger(self):
        d = int32(0)
        CALL ('GetArmStartTrigType', self, ctypes.byref (d))
        if d.value==DAQmx_Val_DigEdge:
            return 'digital_edge'
        if d.value==DAQmx_Val_None:
            return None
        assert 0, `d.value`

    def reset_arm_start_trigger(self):
        return CALL ('ResetArmStartTrigType', self)==0

    def set_arm_start_trigger_source (self, source):
        """
        Specifies the name of a terminal where there is a digital
        signal to use as the source of the Arm Start Trigger.
        """
        source = str (source)
        return CALL ('SetDigEdgeArmStartTrigSrc', self, source)==0

    def set_arm_start_trigger_edge (self, edge='rising'):
        """
        Specifies on which edge of a digital signal to arm the task
        for a Start Trigger.
        """
        edge_map = dict (rising=DAQmx_Val_Rising,
                         falling=DAQmx_Val_Falling)
        edge_val = self._get_map_value ('edge', edge_map, edge)
        return CALL ('SetDigEdgeArmStartTrigEdge', self, edge_val)

    _pause_trigger_type = None
    def set_pause_trigger(self, trigger_type = None):
        trigger_type_map = dict(digital_level = DAQmx_Val_DigLvl,
                                analog_level = DAQmx_Val_AnlgLvl,
                                analog_window = DAQmx_Val_AnlgWin,
                                )
        trigger_type_map[None] = DAQmx_Val_None
        trigger_type_val = self._get_map_value('trigger_type',trigger_type_map, trigger_type)
        self._pause_trigger_type = trigger_type
        return CALL ('SetPauseTrigType', self, trigger_type_val)==0

    def set_pause_trigger_source(self, source):
        """
        Specifies the name of a virtual channel or terminal where
        there is an analog signal to use as the source of the trigger.

        For E Series devices, if you use a channel name, the channel
        must be the only channel in the task. The only terminal you
        can use for E Series devices is PFI0.
        """
        source = str(source)
        if self._pause_trigger_type is None:
            raise TypeError('pause trigger type is not specified')
        routine_map = dict(digital_level = 'SetDigLvlPauseTrigSrc',
                           analog_level = 'SetAnlgLvlPauseTrigSrc',
                           analog_window = 'SetAnlgWinPauseTrigSrc')
        routine = self._get_map_value('set_pause_trigger_src_routine', routine_map, self._pause_trigger_type)
        return CALL (routine, self, source)==0

    def set_pause_trigger_when (self, when = None):
        """
        Specifies whether the task pauses above or below the threshold
        you specify with Level.

        Specifies whether the task pauses while the trigger signal is
        inside or outside the window you specify with Bottom and Top.

        Specifies whether the task pauses while the signal is high or
        low.
        """
        if self._pause_trigger_type is None:
            raise TypeError('pause trigger type is not specified')
        routine_map = dict(digital_level = 'SetDigLvlPauseTrigWhen',
                           analog_level = 'SetAnlgLvlPauseTrigWhen',
                           analog_window = 'SetAnlgWinPauseTrigWhen')
        routine = self._get_map_value('set_pause_trigger_when_routine', routine_map, self._pause_trigger_type)
        type_when_map = dict(digital_level = dict (high = DAQmx_Val_High, low = DAQmx_Val_Low),
                             analog_level = dict (above = DAQmx_Val_AboveLvl, below = DAQmx_Val_BelowLvl),
                             analog_window = dict (inside = DAQmx_Val_InsideWin, outside=DAQmx_Val_OutsideWin))
        when_map = self._get_map_value('set_pause_trigger_when_map', type_when_map, self._pause_trigger_type)
        when_val = self._get_map_value('when', when_map, when)
        return CALL (routine, self, when_val)

    def get_info_str(self, global_info=False):
        lines = []
        tab = ''
        if global_info:
            lines.append(tab+'NIDAQwx version: %s' % (self.get_version()))
            lines.append(tab+'System devices: %s' % (', '.join(self.get_system_devices()) or None))
            lines.append(tab+'System global channels: %s' % (', '.join(self.get_system_global_channels()) or None))
            lines.append(tab+'System tasks: %s' % (', '.join(self.get_system_tasks()) or None))
            tab += '  '
            for device in self.get_system_devices():
                lines.append(tab[:-1]+'Device: %s' % (device))
                lines.append(tab + 'Product type: %s' % (device.get_product_type()))
                lines.append(tab + 'Product number: %s' % (device.get_product_number()))
                lines.append(tab + 'Serial number: %s' % (device.get_serial_number()))
                lines.append (tab+'Bus: %s' % (device.get_bus ()))
                lines.append (tab+'Analog input channels: %s' % (make_pattern(device.get_analog_input_channels()) or None))
                lines.append (tab+'Analog output channels: %s' % (make_pattern(device.get_analog_output_channels()) or None))
                lines.append (tab+'Digital input lines: %s' % (make_pattern(device.get_digital_input_lines()) or None))
                lines.append (tab+'Digital input ports: %s' % (make_pattern(device.get_digital_input_ports()) or None))
                lines.append (tab+'Digital output lines: %s' % (make_pattern(device.get_digital_output_lines()) or None))
                lines.append (tab+'Digital output ports: %s' % (make_pattern(device.get_digital_output_ports()) or None))
                lines.append (tab+'Counter input channels: %s' % (make_pattern(device.get_counter_input_channels()) or None))
                lines.append (tab+'Counter output channels: %s' % (make_pattern(device.get_counter_output_channels()) or None))
        lines.append(tab[:-1]+'Task name: %s' % (self.name))
        lines.append(tab+'Names of devices: %s' % (', '.join(self.get_devices()) or None))
        lines.append(tab+'Number of channels: %s' % (self.get_number_of_channels()))
        lines.append(tab+'Names of channels: %s' % (', '.join(self.get_names_of_channels()) or None))
        lines.append(tab+'Channel type: %s' % (self.channel_type))
        lines.append(tab+'Channel I/O type: %s' % (self.channel_io_type))
        lines.append(tab+'Buffer size: %s' % (self.get_buffer_size()))

        tab += '  '
        for channel_name in self.get_names_of_channels():
            lines.append(tab[:-1]+'Channel name: %s' % (channel_name))
            lines.append(tab+'Physical channel name: %s' % (self.get_physical_channel_name(channel_name)))
            lines.append(tab+'Channel type: %s' % (self.get_channel_type (channel_name)))
            lines.append(tab+'Is global: %s' % (self.is_channel_global(channel_name)))
            if self.channel_type in ['AI', 'AO']:
                lines.append(tab+'Measurment type: %s' % (self.get_measurment_type(channel_name)))
                lines.append(tab+'Minimum/Maximum values: %s/%s %s' % (self.get_min(channel_name),
                                                                   self.get_max(channel_name),
                                                                   self.get_units(channel_name)))
                #lines.append(tab+'Gain: %s' % (self.get_gain (channel_name)))
                lines.append(tab+'Data transfer mechanism: %s' % (self.get_data_transfer_mechanism(channel_name)))
            if self.channel_type=='AI':
                lines.append(tab+'High/Low values: %s/%s' % (self.get_high(channel_name),
                                                             self.get_low (channel_name)))
                lines.append(tab+'Auto zero mode: %s' % (self.get_auto_zero_mode(channel_name)))
        return '\n'.join(lines)

    def get_read_current_position (self):
        """
        Indicates in samples per channel the current position in the
        buffer.
        """
        d = uInt64(0)
        CALL('GetReadCurrReadPos', self, ctypes.byref(d))
        return d.value

    def get_samples_per_channel_available(self):
        """
        Indicates the number of samples available to read per
        channel. This value is the same for all channels in the task.
        """
        d = uInt32(0)
        CALL('GetReadAvailSampPerChan', self, ctypes.byref(d))
        return d.value

    def get_samples_per_channel_acquired(self):
        """
        Indicates the total number of samples acquired by each
        channel. NI-DAQmx returns a single value because this value is
        the same for all channels.
        """
        d = uInt32(0)
        CALL('GetReadTotalSampPerChanAcquired', self, ctypes.byref(d))
        return d.value

    def wait_until_done(self, timeout=-1):
        """
        Waits for the measurement or generation to complete. Use this
        function to ensure that the specified operation is complete
        before you stop the task.

        Parameters:

        timeout - The maximum amount of time, in seconds, to wait for
          the measurement or generation to complete. The function
          returns an error if the time elapses before the measurement or
          generation is complete.
        
          A value of -1 (DAQmx_Val_WaitInfinitely) means to wait
          indefinitely.

          If you set timeout to 0, the function checks once and
          returns an error if the measurement or generation is not
          done.

        """
        return CALL('WaitUntilTaskDone', self, float64 (timeout))==0

class AnalogInputTask(Task):

    channel_type = 'AI'

    def create_voltage_channel(self, phys_channel, channel_name="", terminal='default',
                               min_val = -1, max_val = 1, 
                               units = 'volts', custom_scale_name = None):
        """
        Creates channel(s) to measure voltage and adds the channel(s)
        to the task you specify with taskHandle. If your measurement
        requires the use of internal excitation or you need the
        voltage to be scaled by excitation, call
        DAQmxCreateAIVoltageChanWithExcit.

        Parameters:

        phys_channel - The names of the physical channels to use to
          create virtual channels. You can specify a list or range of
          physical channels.

        channel_name - The name(s) to assign to the created virtual
          channel(s). If you do not specify a name, NI-DAQmx uses the
          physical channel name as the virtual channel name. If you
          specify your own names for nameToAssignToChannel, you must
          use the names when you refer to these channels in other
          NI-DAQmx functions.

          If you create multiple virtual channels with one call to
          this function, you can specify a list of names separated by
          commas. If you provide fewer names than the number of
          virtual channels you create, NI-DAQmx automatically assigns
          names to the virtual channels.

        terminal - The input terminal configuration for the channel:

          'default' - At run time, NI-DAQmx chooses the default
            terminal configuration for the channel.

          'rse' - Referenced single-ended mode
          'nrse' - Nonreferenced single-ended mode
          'diff' - Differential mode
          'pseudodiff' - Pseudodifferential mode 

        min_val - The minimum value, in units, that you expect to measure.

        max_val - The maximum value, in units, that you expect to measure.

        units - The units to use to return the voltage measurements:

          'volts' - volts

          'custom' - Units a custom scale specifies. Use
            custom_scale_name to specify a custom scale.

        custom_scale_name - The name of a custom scale to apply to the
          channel. To use this parameter, you must set units to
          'custom'.  If you do not set units to 'custom', you must set
          custom_scale_name to None.

        Returns True on success.
        """
        phys_channel = str(phys_channel)
        channel_name = str(channel_name)
        terminal_map = dict (default = DAQmx_Val_Cfg_Default,
                             rse = DAQmx_Val_RSE,
                             nrse = DAQmx_Val_NRSE,
                             diff = DAQmx_Val_Diff,
                             pseudodiff = DAQmx_Val_PseudoDiff)
        units_map = dict (volts = DAQmx_Val_Volts,
                          custom = DAQmx_Val_FromCustomScale)

        terminal_val = self._get_map_value ('terminal', terminal_map, terminal.lower())
        units_val = self._get_map_value ('units', units_map, units)

        if units_val==DAQmx_Val_FromCustomScale:
            if custom_scale_name is None:
                raise ValueError ('Must specify custom_scale_name for custom scale.')

        r = CALL('CreateAIVoltageChan', self, phys_channel, channel_name, terminal_val,
                 float64(min_val), float64(max_val), units_val, custom_scale_name)
        self.set_channel_type(self.get_channel_type(channel_name))
        return r==0

    def read(self, samples_per_channel=None, timeout=10.0,
             fill_mode='group_by_scan_number'):
        """
        Reads multiple floating-point samples from a task that
        contains one or more analog input channels.

        Parameters:

        samples_per_channel - The number of samples, per channel, to
          read. The default value of -1 (DAQmx_Val_Auto) reads all
          available samples. If readArray does not contain enough
          space, this function returns as many samples as fit in
          readArray.

          NI-DAQmx determines how many samples to read based on
          whether the task acquires samples continuously or acquires a
          finite number of samples.

          If the task acquires samples continuously and you set this
          parameter to -1, this function reads all the samples
          currently available in the buffer.

          If the task acquires a finite number of samples and you set
          this parameter to -1, the function waits for the task to
          acquire all requested samples, then reads those samples. If
          you set the Read All Available Samples property to TRUE, the
          function reads the samples currently available in the buffer
          and does not wait for the task to acquire all requested
          samples.

        timeout - The amount of time, in seconds, to wait for the
          function to read the sample(s). The default value is 10.0
          seconds. To specify an infinite wait, pass -1
          (DAQmx_Val_WaitInfinitely). This function returns an error
          if the timeout elapses.

          A value of 0 indicates to try once to read the requested
          samples. If all the requested samples are read, the function
          is successful. Otherwise, the function returns a timeout
          error and returns the samples that were actually read.

        fill_mode - Specifies whether or not the samples are
          interleaved:

          'group_by_channel' - Group by channel (non-interleaved).
          'group_by_scan_number' - Group by scan number (interleaved).

        Output:
        
        data - The array to read samples into, organized according to fill_mode.

        Note on data storage order:

        In non-interleaved mode: ch0:s1, ch0:s2, ..., ch1:s1, ch1:s2,..., ch2:s1,..
        In interleaved mode: ch0:s1, ch1:s1, ch2:s1, ch0:s2, ch1:s2, ch2:s2,...

        """
        fill_mode_map = dict(group_by_channel = DAQmx_Val_GroupByChannel,
                             group_by_scan_number = DAQmx_Val_GroupByScanNumber)
        fill_mode_val = self._get_map_value('fill_mode', fill_mode_map, fill_mode)

        if samples_per_channel is None:
            samples_per_channel = self.get_samples_per_channel_available()

        number_of_channels = self.get_number_of_channels()
        if fill_mode=='group_by_scan_number':
            data = np.zeros((samples_per_channel, number_of_channels),dtype=np.float64)
        else:
            data = np.zeros((number_of_channels, samples_per_channel),dtype=np.float64)
        samples_read = int32(0)

        r = CALL('ReadAnalogF64', self, samples_per_channel, float64(timeout),
                 fill_mode_val, data.ctypes.data, data.size, ctypes.byref(samples_read), None)

        if samples_per_channel < samples_read.value:
            if fill_mode=='group_by_scan_number':
                return data[:samples_read.value]
            else:
                return data[:,:samples_read.value]
        return data
    

class AnalogOutputTask (Task):

    channel_type = 'AO'

    def create_voltage_channel(self, phys_channel, channel_name="",
                               min_val = -1, max_val = 1, 
                               units = 'volts', custom_scale_name = None):
        """
        Creates channel(s) to generate voltage and adds the channel(s)
        to the task you specify with taskHandle.

        See also AnalogInputTask.create_voltage_channel method.
        """
        phys_channel = str(phys_channel)
        channel_name = str(channel_name)
        if custom_scale_name is not None:
            custom_scale_name = str(custom_scale_name)
        self.set_channel_type('AO')
        units_map = dict (volts = DAQmx_Val_Volts,
                          custom = DAQmx_Val_FromCustomScale)

        units_val = self._get_map_value ('units', units_map, units)

        if units_val==DAQmx_Val_FromCustomScale:
            if custom_scale_name is None:
                raise ValueError ('Must specify custom_scale_name for custom scale.')

        r = CALL('CreateAOVoltageChan', self, phys_channel, channel_name,
                 float64(min_val), float64(max_val), units_val, custom_scale_name)
        self.set_channel_type(self.get_channel_type(channel_name))
        return r==0    

    def write(self, data,
              auto_start=True, timeout=10.0, layout='group_by_scan_number'):
        """
        Writes multiple floating-point samples or a scalar to a task
        that contains one or more analog output channels.

        Note: If you configured timing for your task, your write is
        considered a buffered write. Buffered writes require a minimum
        buffer size of 2 samples. If you do not configure the buffer
        size using DAQmxCfgOutputBuffer, NI-DAQmx automatically
        configures the buffer when you configure sample timing. If you
        attempt to write one sample for a buffered write without
        configuring the buffer, you will receive an error.

        data - The array of 64-bit samples to write to the task
          or a scalar.

        auto_start - Specifies whether or not this function
          automatically starts the task if you do not start it.

        timeout - The amount of time, in seconds, to wait for this
          function to write all the samples. The default value is 10.0
          seconds. To specify an infinite wait, pass -1
          (DAQmx_Val_WaitInfinitely). This function returns an error
          if the timeout elapses.

          A value of 0 indicates to try once to write the submitted
          samples. If this function successfully writes all submitted
          samples, it does not return an error. Otherwise, the
          function returns a timeout error and returns the number of
          samples actually written.

        layout - Specifies how the samples are arranged, either
          interleaved or noninterleaved:

          'group_by_channel' - Group by channel (non-interleaved).
          'group_by_scan_number' - Group by scan number (interleaved).

          [applies iff data is array]

        Output:

        samples_written - The actual number of samples per channel
          successfully written to the buffer. [applies iff data is array].

        """
        if np.isscalar(data):
            return CALL('WriteAnalogScalar64', self, bool32(auto_start),
                        float64(timeout), float64(data), None)==0

        layout_map = dict(group_by_channel = DAQmx_Val_GroupByChannel,
                          group_by_scan_number = DAQmx_Val_GroupByScanNumber)
        layout_val = self._get_map_value('layout', layout_map, layout)

        samples_written = int32(0)

        data = np.asarray(data, dtype = np.float64)

        number_of_channels = self.get_number_of_channels()

        if len(data.shape)==1:
            if number_of_channels==1:
                assert number_of_channels == 1, `number_of_channels, data.shape`
                samples_per_channel = data.shape[0]
                if layout=='group_by_scan_number':
                    data = data.reshape((samples_per_channel, 1))
                else:
                    data = data.reshape((1, samples_per_channel))
            else:
                samples_per_channel = data.size / number_of_channels
                if layout=='group_by_scan_number':
                    data = data.reshape ((samples_per_channel, number_of_channels))
                else:
                    data = data.reshape ((number_of_channels, samples_per_channel))
        else:
            assert len (data.shape)==2,`data.shape`
            if layout=='group_by_scan_number':
                assert data.shape[-1]==number_of_channels,`data.shape, number_of_channels`
                samples_per_channel = data.shape[0]
            else:
                assert data.shape[0]==number_of_channels,`data.shape, number_of_channels`
                samples_per_channel = data.shape[-1]

        r = CALL('WriteAnalogF64', self, int32(samples_per_channel), bool32(auto_start),
                 float64 (timeout), layout_val, data.ctypes.data, ctypes.byref(samples_written), None)

        return samples_written.value

class DigitalTask (Task):

    def get_number_of_lines(self, channel):
        """
        Indicates the number of digital lines in the channel.
        """
        channel_type = self.channel_type
        assert channel_type in ['DI', 'DO'],`channel_type, channel`
        channel = str (channel)
        d = uInt32(0)
        CALL('Get%sNumLines' % (channel_type), self, channel, ctypes.byref(d))
        return d.value

class DigitalInputTask(DigitalTask):

    channel_type = 'DI'

    def create_channel(self, lines, name='', grouping='per_line'):
        """
        Creates channel(s) to measure digital signals and adds the
        channel(s) to the task you specify with taskHandle. You can
        group digital lines into one digital channel or separate them
        into multiple digital channels. If you specify one or more
        entire ports in lines by using port physical channel names,
        you cannot separate the ports into multiple channels. To
        separate ports into multiple channels, use this function
        multiple times with a different port each time.

        Parameters:
        
        lines - The names of the digital lines used to create a
          virtual channel. You can specify a list or range of lines.

        name - The name of the created virtual channel(s). If you
          create multiple virtual channels with one call to this
          function, you can specify a list of names separated by
          commas. If you do not specify a name, NI-DAQmx uses the
          physical channel name as the virtual channel name. If you
          specify your own names for name, you must use the names when
          you refer to these channels in other NI-DAQmx functions.

        grouping - Specifies whether to group digital lines into one
        or more virtual channels. If you specify one or more entire
        ports in lines, you must set grouping to 'for_all_lines':

          'per_line' - One channel for each line
          'for_all_lines' - One channel for all lines
        """
        lines = str (lines)
        grouping_map = dict(per_line=DAQmx_Val_ChanPerLine,
                            for_all_lines = DAQmx_Val_ChanForAllLines)
        grouping_val = self._get_map_value('grouping', grouping_map, grouping)
        self.one_channel_for_all_lines =  grouping_val==DAQmx_Val_ChanForAllLines
        return CALL('CreateDIChan', self, lines, name, grouping_val)==0

    def read(self, samples_per_channel=None, timeout=10.0, fill_mode='group_by_scan_number'):
        """
        Reads multiple samples from each digital line in a task. Each
        line in a channel gets one byte per sample.

        Parameters:

        samples_per_channel - The number of samples, per channel, to
          read. The default value of -1 (DAQmx_Val_Auto) reads all
          available samples. If readArray does not contain enough
          space, this function returns as many samples as fit in
          readArray.

          NI-DAQmx determines how many samples to read based on
          whether the task acquires samples continuously or acquires a
          finite number of samples.

          If the task acquires samples continuously and you set this
          parameter to -1, this function reads all the samples
          currently available in the buffer.

          If the task acquires a finite number of samples and you set
          this parameter to -1, the function waits for the task to
          acquire all requested samples, then reads those samples. If
          you set the Read All Available Data property to TRUE, the
          function reads the samples currently available in the buffer
          and does not wait for the task to acquire all requested
          samples.

        timeout - The amount of time, in seconds, to wait for the
          function to read the sample(s). The default value is 10.0
          seconds. To specify an infinite wait, pass -1
          (DAQmx_Val_WaitInfinitely). This function returns an error
          if the timeout elapses.

          A value of 0 indicates to try once to read the requested
          samples. If all the requested samples are read, the function
          is successful. Otherwise, the function returns a timeout
          error and returns the samples that were actually read.

        fill_mode - Specifies whether or not the samples are
          interleaved:

          'group_by_channel' - Group by channel (non-interleaved).
          'group_by_scan_number' - Group by scan number (interleaved).

        Output:

          data - The array to read samples into. Each numBytesPerSamp
            corresponds to one sample per channel, with each element
            in that grouping corresponding to a line in that channel,
            up to the number of lines contained in the channel.

          bytes_per_sample - The number of elements in readArray that
            constitutes a sample per channel. For each sample per
            channel, numBytesPerSamp is the number of bytes that
            channel consists of.

        """
        fill_mode_map = dict(group_by_channel = DAQmx_Val_GroupByChannel,
                             group_by_scan_number = DAQmx_Val_GroupByScanNumber)
        fill_mode_val = self._get_map_value('fill_mode', fill_mode_map, fill_mode)

        if samples_per_channel in [None,-1]:
            samples_per_channel = self.get_samples_per_channel_available()

        if self.one_channel_for_all_lines:
            nof_lines = []
            for channel in self.get_names_of_channels():
                nof_lines.append(self.get_number_of_lines (channel))
            c = int (max (nof_lines))
            dtype = getattr(np, 'uint%s'%(8 * c))
        else:
            c = 1
            dtype = np.uint8
        number_of_channels = self.get_number_of_channels()
        if fill_mode=='group_by_scan_number':
            data = np.zeros((samples_per_channel, number_of_channels),dtype=dtype)
        else:
            data = np.zeros((number_of_channels, samples_per_channel),dtype=dtype)

        samples_read = int32(0)
        bytes_per_sample = int32(0)

        CALL ('ReadDigitalLines', self, samples_per_channel, float64 (timeout),
              fill_mode_val, data.ctypes.data, uInt32 (data.size * c), 
              ctypes.byref (samples_read), ctypes.byref (bytes_per_sample),
              None
              )
        if samples_read.value < samples_per_channel:
            if fill_mode=='group_by_scan_number':
                return data[:samples_read.value], bytes_per_sample.value
            else:
                return data[:,:samples_read.value], bytes_per_sample.value
        return data, bytes_per_sample.value


class DigitalOutputTask(DigitalTask):

    channel_type = 'DO'

    def create_channel(self, lines, name='', grouping='per_line'):
        """
        Creates channel(s) to generate digital signals and adds the
        channel(s) to the task you specify with taskHandle. You can
        group digital lines into one digital channel or separate them
        into multiple digital channels. If you specify one or more
        entire ports in lines by using port physical channel names,
        you cannot separate the ports into multiple channels. To
        separate ports into multiple channels, use this function
        multiple times with a different port each time.

        Parameters:
        
        lines - The names of the digital lines used to create a
          virtual channel. You can specify a list or range of lines.

        name - The name of the created virtual channel(s). If you
          create multiple virtual channels with one call to this
          function, you can specify a list of names separated by
          commas. If you do not specify a name, NI-DAQmx uses the
          physical channel name as the virtual channel name. If you
          specify your own names for name, you must use the names when
          you refer to these channels in other NI-DAQmx functions.

        grouping - Specifies whether to group digital lines into one
        or more virtual channels. If you specify one or more entire
        ports in lines, you must set grouping to 'for_all_lines':

          'per_line' - One channel for each line
          'for_all_lines' - One channel for all lines
        """
        lines = str (lines)
        grouping_map = dict(per_line=DAQmx_Val_ChanPerLine,
                            for_all_lines = DAQmx_Val_ChanForAllLines)
        grouping_val = self._get_map_value('grouping', grouping_map, grouping)
        return CALL('CreateDOChan', self, lines, name, grouping_val)==0

    def write(self, data, 
              auto_start=True, timeout=10.0, 
              layout='group_by_channel'):
        """
        Writes multiple samples to each digital line in a task. When
        you create your write array, each sample per channel must
        contain the number of bytes returned by the
        DAQmx_Read_DigitalLines_BytesPerChan property.

	Note: If you configured timing for your task, your write is
	considered a buffered write. Buffered writes require a minimum
	buffer size of 2 samples. If you do not configure the buffer
	size using DAQmxCfgOutputBuffer, NI-DAQmx automatically
	configures the buffer when you configure sample timing. If you
	attempt to write one sample for a buffered write without
	configuring the buffer, you will receive an error.

        Parameters:
        
        data - The samples to write to the task.

        auto_start - Specifies whether or not this function
          automatically starts the task if you do not start it.

        timeout - The amount of time, in seconds, to wait for this
          function to write all the samples. The default value is 10.0
          seconds. To specify an infinite wait, pass -1
          (DAQmx_Val_WaitInfinitely). This function returns an error
          if the timeout elapses.

          A value of 0 indicates to try once to write the submitted
          samples. If this function successfully writes all submitted
          samples, it does not return an error. Otherwise, the
          function returns a timeout error and returns the number of
          samples actually written.

        layout - Specifies how the samples are arranged, either
          interleaved or noninterleaved:

          'group_by_channel' - Group by channel (non-interleaved).
          'group_by_scan_number' - Group by scan number (interleaved).
        """
        layout_map = dict(group_by_channel = DAQmx_Val_GroupByChannel,
                          group_by_scan_number = DAQmx_Val_GroupByScanNumber)
        layout_val = self._get_map_value('layout', layout_map, layout)
        samples_written = int32(0)

        number_of_channels = self.get_number_of_channels()

        if np.isscalar(data):
            data = np.array([data]*number_of_channels, dtype = np.uint8)
        else:
            data = np.asarray(data, dtype = np.uint8)

        if len(data.shape)==1:
            assert number_of_channels == 1, `number_of_channels, data.shape`
            samples_per_channel = data.shape[0]
            if layout=='group_by_scan_number':
                data = data.reshape((samples_per_channel, 1))
            else:
                data = data.reshape((1, samples_per_channel))
        else:
            assert len (data.shape)==2,`data.shape`
            if layout=='group_by_scan_number':
                assert data.shape[-1]==number_of_channels,`data.shape, number_of_channels`
                samples_per_channel = data.shape[0]
            else:
                assert data.shape[0]==number_of_channels,`data.shape, number_of_channels`
                samples_per_channel = data.shape[-1]

        r = CALL('WriteDigitalLines', self, samples_per_channel, 
                 bool32(auto_start),
                 float64(timeout), layout_val, 
                 data.ctypes.data, ctypes.byref(samples_written), None)

        return samples_written.value

    # NotImplemented: WriteDigitalU8, WriteDigitalU16, WriteDigitalU32, WriteDigitalScalarU32

class CounterInputTask(Task):

    channel_type = 'CI'

    def create_channel_count_edges (self, counter, name="", edge='rising',
                                    init=0, direction='up'):
        """
        Creates a channel to count the number of rising or falling
        edges of a digital signal and adds the channel to the task you
        specify with taskHandle. You can create only one counter input
        channel at a time with this function because a task can
        include only one counter input channel. To read from multiple
        counters simultaneously, use a separate task for each
        counter. Connect the input signal to the default input
        terminal of the counter unless you select a different input
        terminal.

        Parameters:

        counter - The name of the counter to use to create virtual
          channels.

        name - The name(s) to assign to the created virtual
          channel(s). If you do not specify a name, NI-DAQmx uses the
          physical channel name as the virtual channel name. If you
          specify your own names for nameToAssignToChannel, you must
          use the names when you refer to these channels in other
          NI-DAQmx functions.

          If you create multiple virtual channels with one call to
          this function, you can specify a list of names separated by
          commas. If you provide fewer names than the number of
          virtual channels you create, NI-DAQmx automatically assigns
          names to the virtual channels.

        edge - Specifies on which edges of the input signal to
          increment or decrement the count:

          'rising' - Rising edge(s).
          'falling' - Falling edge(s).

        init - The value from which to start counting.

        direction - Specifies whether to increment or decrement the
          counter on each edge:

          'up' - Increment the count register on each edge.
          'down' - Decrement the count register on each edge.
          'ext' - The state of a digital line controls the count
            direction. Each counter has a default count direction
            terminal.

        """
        counter = str(counter)
        name = str(name)
        edge_map = dict (rising=DAQmx_Val_Rising, falling=DAQmx_Val_Falling)
        direction_map = dict (up=DAQmx_Val_CountUp, down=DAQmx_Val_CountDown,
                              ext=DAQmx_Val_ExtControlled)
        edge_val = self._get_map_value ('edge', edge_map, edge)
        direction_val = self._get_map_value ('direction', direction_map, direction)
        return CALL ('CreateCICountEdgesChan', self, counter, name, edge_val, direction_val)==0

    def set_terminal_count_edges(self, channel, terminal):
        """
        Specifies the input terminal of the signal to measure.
        """
        return CALL('SetCICountEdgesTerm', self, channel, terminal)==0

class CounterOutputTask(Task):
    
    channel_type = 'CO'

    def create_channel_frequency(self, counter, name="", units='hertz', idle_state='low',
                                 delay=0.0, freq=1.0, duty_cycle=0.5):
        """
        Creates channel(s) to generate digital pulses that freq and
        duty_cycle define and adds the channel to the task.  The
        pulses appear on the default output terminal of the counter
        unless you select a different output terminal.

        Parameters:

        counter - The name of the counter to use to create virtual
          channels. You can specify a list or range of physical
          channels.

        name - The name(s) to assign to the created virtual
          channel(s). If you do not specify a name, NI-DAQmx uses the
          physical channel name as the virtual channel name. If you
          specify your own names for nameToAssignToChannel, you must
          use the names when you refer to these channels in other
          NI-DAQmx functions.

          If you create multiple virtual channels with one call to
          this function, you can specify a list of names separated by
          commas. If you provide fewer names than the number of
          virtual channels you create, NI-DAQmx automatically assigns
          names to the virtual channels.

        units - The units in which to specify freq:

          'hertz' - hertz

        idle_state - The resting state of the output terminal:

          'low' - Low state.
          'high' - High state.

        delay - The amount of time in seconds to wait before
          generating the first pulse.

        freq - The frequency at which to generate pulses.

        duty_cycle - The width of the pulse divided by the pulse
          period. NI-DAQmx uses this ratio, combined with frequency,
          to determine pulse width and the interval between pulses.

        """
        counter = str(counter)
        name = str(name)
        units_map = dict (hertz = DAQmx_Val_Hz)
        idle_state_map = dict (low=DAQmx_Val_Low, high=DAQmx_Val_High)
        units_val = self._get_map_value('units', units_map, units)
        idle_state_val = self._get_map_value('idle_state', idle_state_map, idle_state)
        return CALL('CreateCOPulseChanFreq', self, counter, name, units_val, idle_state_val,
                    float64(delay), float64(freq), float64(duty_cycle))==0

    def create_channel_ticks(self, counter, name="", source="", idle_state='low',
                             delay = 0, low_ticks=1, high_ticks=1):
        """
        Creates channel(s) to generate digital pulses defined by the
        number of timebase ticks that the pulse is at a high state and
        the number of timebase ticks that the pulse is at a low state
        and also adds the channel to the task. The pulses appear on
        the default output terminal of the counter unless you select a
        different output terminal.

        Parameters:

        counter - The name of the counter to use to create virtual
          channels. You can specify a list or range of physical
          channels.

        name - The name(s) to assign to the created virtual
          channel(s). If you do not specify a name, NI-DAQmx uses the
          physical channel name as the virtual channel name. If you
          specify your own names for nameToAssignToChannel, you must
          use the names when you refer to these channels in other
          NI-DAQmx functions.

          If you create multiple virtual channels with one call to
          this function, you can specify a list of names separated by
          commas. If you provide fewer names than the number of
          virtual channels you create, NI-DAQmx automatically assigns
          names to the virtual channels.

        source - The terminal to which you connect an external
          timebase. You also can specify a source terminal by using a
          terminal name.

        idle_state - The resting state of the output terminal:

          'low' - Low state.
          'high' - High state.


        delay - The number of timebase ticks to wait before generating
          the first pulse.

        low_ticks - The number of timebase ticks that the pulse is
          low.

        high_ticks - The number of timebase ticks that the pulse is
          high.
        """
        counter = str(counter)
        name = str(name)
        idle_state_map = dict (low=DAQmx_Val_Low, high=DAQmx_Val_High)
        idle_state_val = self._get_map_value('idle_state', idle_state_map, idle_state)
        return CALL('CreateCOPulseChanTicks', self, counter, name, source, idle_state_val,
                    int32 (delay), int32 (low_ticks), int32 (high_ticks))==0

    def create_channel_time(self, counter, name="", units="seconds", idle_state='low',
                             delay = 0, low_time=1, high_time=1):
        """
        Creates channel(s) to generate digital pulses defined by the
        number of timebase ticks that the pulse is at a high state and
        the number of timebase ticks that the pulse is at a low state
        and also adds the channel to the task. The pulses appear on
        the default output terminal of the counter unless you select a
        different output terminal.

        Parameters:

        counter - The name of the counter to use to create virtual
          channels. You can specify a list or range of physical
          channels.

        name - The name(s) to assign to the created virtual
          channel(s). If you do not specify a name, NI-DAQmx uses the
          physical channel name as the virtual channel name. If you
          specify your own names for nameToAssignToChannel, you must
          use the names when you refer to these channels in other
          NI-DAQmx functions.

          If you create multiple virtual channels with one call to
          this function, you can specify a list of names separated by
          commas. If you provide fewer names than the number of
          virtual channels you create, NI-DAQmx automatically assigns
          names to the virtual channels.

        units - The units in which to specify high and low time:

          'seconds' - seconds

        idle_state - The resting state of the output terminal:

          'low' - Low state.
          'high' - High state.


        delay - The amount of time in seconds to wait before
          generating the first pulse.

        low_time - The amount of time the pulse is low, in seconds.

        high_time - The amount of time the pulse is high, in seconds.
        """
        counter = str(counter)
        name = str(name)
        units_map = dict (seconds = DAQmx_Val_Seconds)
        idle_state_map = dict (low=DAQmx_Val_Low, high=DAQmx_Val_High)
        units_val = self._get_map_value('units', units_map, units)
        idle_state_val = self._get_map_value('idle_state', idle_state_map, idle_state)
        return CALL('CreateCOPulseChanTime', self, counter, name, units_val, idle_state_val,
                    float64 (delay), float64(low_time), float64(high_time))==0

    def set_terminal_pulse (self, channel, terminal):
        """
        Specifies on which terminal to generate pulses.
        """
        channel = str(channel)
        terminal = str(terminal)
        return CALL ('SetCOPulseTerm', self, channel, terminal)==0

DoneEventCallback_map = dict(AI=ctypes.CFUNCTYPE (int32, AnalogInputTask, int32, void_p),
                             AO=ctypes.CFUNCTYPE (int32, AnalogOutputTask, int32, void_p),
                             DI=ctypes.CFUNCTYPE (int32, DigitalInputTask, int32, void_p),
                             DO=ctypes.CFUNCTYPE (int32, DigitalOutputTask, int32, void_p),
                             CI=ctypes.CFUNCTYPE (int32, CounterInputTask, int32, void_p),
                             CO=ctypes.CFUNCTYPE (int32, CounterOutputTask, int32, void_p),
                             )
EveryNSamplesEventCallback_map = dict(AI=ctypes.CFUNCTYPE (int32, AnalogInputTask, int32, uInt32, void_p),
                                      AO=ctypes.CFUNCTYPE (int32, AnalogOutputTask, int32, uInt32, void_p),
                                      DI=ctypes.CFUNCTYPE (int32, DigitalInputTask, int32, uInt32, void_p),
                                      DO=ctypes.CFUNCTYPE (int32, DigitalOutputTask, int32, uInt32, void_p),
                                      CI=ctypes.CFUNCTYPE (int32, CounterInputTask, int32, uInt32, void_p),
                                      CO=ctypes.CFUNCTYPE (int32, CounterOutputTask, int32, uInt32, void_p),
                                      )
SignalEventCallback_map = dict(AI=ctypes.CFUNCTYPE (int32, AnalogInputTask, int32, void_p),
                               AO=ctypes.CFUNCTYPE (int32, AnalogOutputTask, int32, void_p),
                               DI=ctypes.CFUNCTYPE (int32, DigitalInputTask, int32, void_p),
                               DO=ctypes.CFUNCTYPE (int32, DigitalOutputTask, int32, void_p),
                               CI=ctypes.CFUNCTYPE (int32, CounterInputTask, int32, void_p),
                               CO=ctypes.CFUNCTYPE (int32, CounterOutputTask, int32, void_p),
                               )

if __name__=='__main__':
    #_test_make_pattern()
    pass

if 0:

    t = AnalogInputTask('measure voltage')
    t.create_voltage_channel('Dev1/ai8', 'measure')
    t.configure_timing_sample_clock()

    g = AnalogOutputTask('generate voltage')
    g.create_voltage_channel('Dev1/ao2', 'generate')


    print t.get_info_str(True)
    print g.get_info_str()
