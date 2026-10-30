"""Live input from KrakenSDR (5 coherent channels): ch0 = reference Yagi, ch1..4 = surveillance.

The KrakenSDR DAQ firmware (krakensdr_daq) streams coherent IQ frames over TCP (port 5000).
Sketch only: frame header layout is defined in heimdall_daq_fw/Firmware/_daq_core/iq_header.py.
Use the official `iq_header.py` to parse, then pass numpy arrays to the pipeline.
"""


def frames(host="127.0.0.1", port=5000):
    raise NotImplementedError("import heimdall iq_header, read frames, yield (ref, surv[4]) complex64 arrays")
