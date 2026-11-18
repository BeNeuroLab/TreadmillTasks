from array import array
import pyb
from . import hardware as hw

class pyControlError(BaseException): # Exception for pyControl errors.
    pass

# Constants used to indicate event types, corresponding event tuple indicated in comment.

event_typ = const(1) # External event   : (time, event_typ, event_ID) 
state_typ = const(2) # State transition : (time, state_typ, state_ID) 
timer_typ = const(3) # User timer       : (time, timer_typ, event_ID) 
print_typ = const(4) # User print       : (time, print_typ, print_string)
hardw_typ = const(5) # Harware callback : (time, hardw_typ, hardware_ID)
stopf_typ = const(6) # Stop framework   : (time, stopf_typ, None)
varbl_typ = const(7) # Variable change  : (time, varbl_typ, (v_name, v_str))

# Event_queue -----------------------------------------------------------------

class Event_queue():
    def __init__(self, max_length=None, max_bytes=None):
        self.max_length = max_length
        self.max_bytes = max_bytes
        self.reset()

    def reset(self):
        self.Q = []
        self.available = False
        self.queued_bytes = 0
        self.dropped = 0
        self.reported_dropped = 0

    def _cost(self, event):
        # Conservative accounting for Python strings and queue entries.
        if event[1] == print_typ:
            return 64 + 4 * len(event[2])
        if event[1] == varbl_typ:
            return 64 + 4 * (len(event[2][0]) + len(event[2][1]))
        return 64

    def put(self, event_tuple):
        cost = self._cost(event_tuple) if self.max_bytes else 0
        # Permit one oversized message in an empty queue, retaining compatibility
        # with task variable dumps. No second entry can accumulate behind it.
        if ((self.max_length is not None and len(self.Q) >= self.max_length) or
                (self.max_bytes is not None and self.Q and
                 self.queued_bytes + cost > self.max_bytes)):
            if self.dropped < 0x3fffffff:
                self.dropped += 1
            return False
        self.Q.append(event_tuple)
        self.queued_bytes += cost
        self.available = True
        return True

    def get(self):
        event = self.Q.pop(0)
        self.available = bool(self.Q)
        if self.max_bytes:
            self.queued_bytes -= self._cost(event)
        return event


class USB_transmitter():
    """One pending immutable frame; all protocol writers share this owner."""
    def __init__(self):
        self.reset()

    def reset(self):
        self.pending = None
        self.chunk = None
        self.offset = 0
        self.channel = None
        self.slot = None
        self.failed = False

    def start(self, packet, channel=None, slot=None):
        assert self.pending is None, 'Cannot interleave outgoing frames.'
        self.pending = memoryview(packet)
        self.chunk = self.pending[:64]
        self.offset = 0
        self.channel = channel
        self.slot = slot

    def service(self):
        if self.pending is None:
            return
        if self.failed:
            raise pyControlError('recording_incomplete: USB frame failed; reset the connection.')
        # At most 64 bytes and one non-waiting USB call per scheduler iteration.
        # Reuse the view when stalled; repeated zero writes must not make garbage.
        try:
            sent = usb_serial.send(self.chunk, timeout=0)
        except BaseException:
            # Accepted byte count is unknown; retrying could duplicate a prefix.
            self.failed = True
            raise
        if sent is None:
            sent = 0
        if sent < 0 or sent > len(self.chunk):
            self.failed = True
            raise pyControlError('Invalid USB send byte count.')
        self.offset += sent
        if self.offset == len(self.pending):
            if self.channel is not None:
                self.channel._release_buffer(self.slot)
            self.reset()
        elif sent:
            self.chunk = self.pending[self.offset:self.offset + 64]


# Timer -----------------------------------------------------------------------

class Timer():

    def __init__(self):
        self.reset()

    def reset(self):
        self.active_timers = [] # list of event tuples: (trigger_time, event_type, data)
        self.paused_timers = [] # list of event tuples: (trigger_time, event_type, data)
        self.available = False
    
    def set(self, interval, event_type, event_data):
        # Set a timer to trigger specified event after 'interval' ms has elapsed.
        global current_time
        self.active_timers.append((current_time+int(interval), event_type, event_data))
        self.active_timers.sort(reverse=True)

    def check(self):
        #Check whether timers have triggered.
        global current_time, check_timers
        self.available = bool(self.active_timers) and (self.active_timers[-1][0] <= current_time)
        check_timers = False

    def get(self):
        # Get first timer event.
        global current_time
        event_tuple = self.active_timers.pop()
        self.available = bool(self.active_timers) and (self.active_timers[-1][0] <= current_time)
        return event_tuple

    def disarm(self, event_ID):
        # Remove all user timers with specified event_ID.
        self.active_timers = [t for t in self.active_timers 
                              if not (t[2] == event_ID and (t[1] in (event_typ, timer_typ)))]
        self.paused_timers = [t for t in self.paused_timers if not t[2] == event_ID]

    def pause(self, event_ID):
        # Pause all user timers with specified event_ID.
        global current_time
        self.paused_timers += [(t[0]-current_time,t[1], t[2]) for t in self.active_timers 
                               if (t[2] == event_ID and (t[1] in (event_typ, timer_typ)))]
        self.active_timers = [t for t in self.active_timers 
                              if not (t[2] == event_ID and (t[1] in (event_typ, timer_typ)))]

    def unpause(self, event_ID):
        # Unpause user timers with specified event.
        global current_time
        self.active_timers += [(t[0]+current_time,t[1], t[2]) for t in self.paused_timers if t[2] == event_ID]
        self.paused_timers = [t for t in self.paused_timers if not t[2] == event_ID]
        self.active_timers.sort(reverse=True)

    def remaining(self,event_ID):
        # Return time until timer for specified event elapses, returns 0 if no timer set for event.
        global current_time
        try:
            return next(t[0]-current_time for t in reversed(self.active_timers) 
                        if (t[1] == event_typ and t[2] == event_ID))
        except StopIteration:
            return 0

    def disarm_type(self, event_type):
        # Disarm all active timers of a particular type.
        self.active_timers = [t for t in self.active_timers if not t[1] == event_type]

# Framework variables and objects ---------------------------------------------

state_machine = None  # State machine object.

timer = Timer()  # Instantiate timer_array object.

event_queue = Event_queue() # Instantiate event que object.

data_output_queue = Event_queue(max_length=256, max_bytes=16384)
transmitter = USB_transmitter()
stream_channel_index = 0
prefer_analog = True
next_diagnostic_time = 0
diagnostic_channel_index = 0
output_incomplete = False
DRAIN_TIMEOUT_MS = 5000

data_output = True  # Whether to output data to the serial line.

current_time = None # Time since run started (milliseconds).

running = False     # Set to True when framework is running, set to False to stop run.

usb_serial = pyb.USB_VCP()  # USB serial port object.

states = {} # Dictionary of {state_name: state_ID}

events = {} # Dictionary of {event_name: event_ID}

ID2name = {} # Dictionary of {ID: state_or_event_name}

clock = pyb.Timer(1) # Timer which generates clock tick.

check_timers = False # Flag to say timers need to be checked, set True by clock tick.

start_time = 0 # Time at which framework run is started.

# Framework functions ---------------------------------------------------------

def _clock_tick(timer):
    # Set flag to check timers, called by hardware timer once each millisecond.
    global check_timers, current_time, start_time
    current_time = pyb.elapsed_millis(start_time)
    check_timers = True

def register_machine(sm):
    global state_machine, states, events, ID2name
    # Adds state machine states and events to framework states and events dicts,
    # if IDs are provided, checks these are valid, otherwise asign IDs.
    assert (type(sm.smd.states) in (dict, list) and (type(sm.smd.states) == type(sm.smd.events))), \
        'States and events must both be lists or both be dicts'

    if type(sm.smd.states) == list: # Assign IDs
        states = {s: i+1 for s, i in zip(sm.smd.states, range(len(sm.smd.states)))}
        events = {e: i+1+len(sm.smd.states)
                  for e, i in zip(sm.smd.events, range(len(sm.smd.events)))}
        sm.smd.states = states 
        sm.smd.events = events

    else: # Check IDs are valid.
        IDs = list(sm.smd.states.values()) + list(sm.smd.events.values())
        assert all([type(i) == int and i > 0 for i in IDs]) and len(set(IDs)) == len(IDs), \
            'Event and state IDs must be unique positive integers.'

    ID2name = {ID: name for name, ID in list(states.items()) + list(events.items())}
    state_machine = sm

def get_events():
    # Print events as dict.
    print(events)

def get_states():
    # Print states as a dict.
    print(states)

def get_variables():
    # Print state machines variables as dict {v_name: repr(v_value)}
    print({k: repr(v) for k, v in state_machine.variables.__dict__.items()})

def output_data(event):
    # Serialize once in the main loop; retain the whole frame across short sends.
    if event[1] in (event_typ, state_typ):
        timestamp = event[0].to_bytes(4, 'little')
        ID = event[2].to_bytes(2, 'little')
        checksum = (sum(timestamp + ID) & 0xffff).to_bytes(2, 'little')
        packet = b'\x07D' + timestamp + ID + checksum
    elif event[1] in (print_typ, varbl_typ):
        if event[1] == print_typ:
            start_byte = b'\x07P'
            data_bytes = event[2].encode()
        else:
            start_byte = b'\x07V'
            data_bytes = event[2][0].encode() + b' ' + event[2][1].encode()
        data_len = len(data_bytes).to_bytes(2, 'little')
        timestamp = event[0].to_bytes(4, 'little')
        checksum = ((sum(data_len + timestamp) + sum(data_bytes)) & 0xffff).to_bytes(2, 'little')
        packet = start_byte + data_len + timestamp + checksum + data_bytes
    else:
        raise pyControlError('Unsupported outgoing event type.')
    transmitter.start(packet)


def _start_analog_frame():
    global stream_channel_index
    count = len(hw.data_channels)
    for _ in range(count):
        channel = hw.data_channels[stream_channel_index]
        stream_channel_index = (stream_channel_index + 1) % count
        if channel._process_streaming():
            return True
    return False


def _report_overruns(force=False):
    global next_diagnostic_time, diagnostic_channel_index
    if not force and current_time < next_diagnostic_time:
        return False
    next_diagnostic_time = current_time + 1000
    count = len(hw.data_channels)
    # Include the event queue in the rotation so neither axis can monopolize
    # the once-per-second diagnostic allowance during sustained overload.
    for _ in range(count + 1):
        index = diagnostic_channel_index
        diagnostic_channel_index = (diagnostic_channel_index + 1) % (count + 1)
        if index == count:
            if data_output_queue.dropped != data_output_queue.reported_dropped:
                data_output_queue.reported_dropped = data_output_queue.dropped
                output_data((current_time, print_typ,
                    'recording_overrun dropped_output_events={}'.format(data_output_queue.dropped)))
                return True
            continue
        channel = hw.data_channels[index]
        if channel.dropped_samples != channel.reported_dropped_samples:
            irq_state = pyb.disable_irq()
            samples = channel.dropped_samples
            blocks = channel.dropped_blocks
            pyb.enable_irq(irq_state)
            channel.reported_dropped_samples = samples
            output_data((current_time, print_typ,
                'recording_overrun channel={} dropped_blocks={} dropped_samples={}'.format(
                    channel.name, blocks, samples)))
            return True
    return False


def service_output(draining=False):
    global prefer_analog
    if transmitter.pending is None:
        if not _report_overruns(force=draining):
            started = False
            if prefer_analog:
                started = _start_analog_frame()
            if not started and data_output_queue.available:
                output_data(data_output_queue.get())
                started = True
            if not started and not prefer_analog:
                _start_analog_frame()
            prefer_analog = not prefer_analog
    transmitter.service()


def _output_pending():
    return (transmitter.pending is not None or data_output_queue.available or
        data_output_queue.dropped != data_output_queue.reported_dropped or
        any(channel.ready_count or (not channel.recording and channel.write_index) or
            channel.dropped_samples != channel.reported_dropped_samples
            for channel in hw.data_channels))


def drain_output(timeout_ms=DRAIN_TIMEOUT_MS):
    global output_incomplete
    started = pyb.millis()
    try:
        while _output_pending():
            if pyb.elapsed_millis(started) >= timeout_ms:
                raise pyControlError('recording_incomplete: USB drain timed out; reset the connection before another run.')
            service_output(draining=True)
            if transmitter.pending is not None:
                pyb.delay(1)
    except BaseException:
        output_incomplete = True
        raise


def recieve_data():
    # Read and process data from computer.
    global running
    new_byte = usb_serial.read(1) 
    if new_byte == b'\x03': # Serial command to stop run.
        running = False
    elif new_byte == b'V': # Get/set variables command.
        data_len = int.from_bytes(usb_serial.read(2), 'little')
        data = usb_serial.read(data_len)
        checksum = int.from_bytes(usb_serial.read(2), 'little')
        if not checksum == (sum(data) & 0xFFFF):
            return  # Bad checksum.
        if data[-1:] == b's': # Set variable.
            v_name, v_str = eval(data[:-1])
            if state_machine._set_variable(v_name, v_str):
                data_output_queue.put((current_time, varbl_typ, (v_name, v_str)))
        elif data[-1:] == b'g': # Get variable.
            v_name = data[:-1].decode()
            v_str = state_machine._get_variable(v_name)
            data_output_queue.put((current_time, varbl_typ, (v_name, v_str)))

def run(duration=None):
    # Always quiesce hardware, including failed starts and task exceptions.
    global current_time, start_time, running, check_timers
    global stream_channel_index, prefer_analog, next_diagnostic_time, diagnostic_channel_index
    if output_incomplete or transmitter.pending is not None:
        raise pyControlError('recording_incomplete: previous drain unfinished; reset the connection.')
    timer.reset()
    event_queue.reset()
    data_output_queue.reset()
    stream_channel_index = 0
    prefer_analog = True
    next_diagnostic_time = 0
    diagnostic_channel_index = 0
    current_time = 0
    check_timers = False
    error = None
    task_started = False
    try:
        if not hw.initialised:
            hw.initialise()
        hw.run_start()
        start_time = pyb.millis()
        clock.init(freq=1000)
        clock.callback(_clock_tick)
        usb_serial.setinterrupt(-1)
        running = True
        task_started = True
        state_machine._start()
        if duration:
            timer.set(duration * 1000, stopf_typ, None)
        while running:
            hw.check_faults()
            # Poll stop/variable commands independently of output backpressure.
            if usb_serial.any():
                recieve_data()
            if not running:
                break
            if hw.interrupt_queue.available:
                hw.IO_dict[hw.interrupt_queue.get()]._process_interrupt()
            elif event_queue.available:
                event = event_queue.get()
                data_output_queue.put(event)
                state_machine._process_event(ID2name[event[2]])
            elif check_timers:
                timer.check()
            elif timer.available:
                event = timer.get()
                if event[1] == timer_typ:
                    state_machine._process_event(ID2name[event[2]])
                elif event[1] == event_typ:
                    data_output_queue.put(event)
                    state_machine._process_event(ID2name[event[2]])
                elif event[1] == hardw_typ:
                    hw.IO_dict[event[2]]._timer_callback()
                elif event[1] == state_typ:
                    state_machine.goto_state(ID2name[event[2]])
                elif event[1] == stopf_typ:
                    running = False
            service_output()
    except BaseException as exception:
        error = exception
    finally:
        running = False
        try:
            clock.deinit()
        except BaseException as exception:
            if error is None:
                error = exception
        try:
            hw.run_stop()
        except BaseException as exception:
            if error is None:
                error = exception
        if task_started:
            try:
                state_machine._stop()
            except BaseException as exception:
                if error is None:
                    error = exception
        try:
            drain_output()
        except BaseException as exception:
            # The host must mark timeout/unfinished framing as incomplete.
            if error is None:
                error = exception
        usb_serial.setinterrupt(3)
    if error is not None:
        raise error
