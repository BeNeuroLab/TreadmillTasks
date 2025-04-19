"""
Test bidirectional UART on Port12 (UART1 @ 9 600 baud).

* Echoes anything received from the PC
* Sends heartbeat 200 every 500 ms
* Prints every TX and RX value in the GUI console
"""

from pyControl.utility import *
from devices import *
from pyControl.hardware import *
from machine import Timer

# ---------- hardware definition --------------------------------------
bci = UARTlink('bci_link', timer_freq=200)   # 2×(100 Hz PC poll)

# ---------- states and events ----------------------------------------
states = ['run']
events = ['heartbeat','bci_link']
initial_state = 'run'

# ---------- behaviour ------------------------------------------------
def run(event):
    if event == 'entry':
        set_timer('heartbeat', 500)

    elif event == 'heartbeat':
        bci.send_int(200)
        print('TASK TX→PC : 200 (heartbeat)')
        set_timer('heartbeat', 500)

    # ---------- async RX via interrupt queue -------------------------
    elif event == 'bci_link':               # device name becomes event
        val = bci.spk                       # latest 2‑byte int
        print('TASK RX←PC : '.format(val))
        bci.send_int(val)                   # echo back
        print('TASK TX→PC : (echo)'.format(val))
