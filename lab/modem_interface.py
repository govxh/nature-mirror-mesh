# Nature-Mirror Mesh — ModemInterface: a Reticulum Interface whose
# physical layer is the project's nmm_modem (16-FSK + RS FEC) played
# through a simulated Watterson HF channel.
#
# This file is the canonical source. modem_mesh_test.py copies it
# verbatim into each node process's <configdir>/interfaces/ directory,
# where Reticulum (RNS >= 1.x) loads it as an *external interface*:
# the config names `type = ModemInterface`, Reticulum execs this file
# with the globals `Interface` (RNS.Interfaces.Interface.Interface) and
# `RNS` predefined, and instantiates `interface_class` below with
# (RNS.Transport, interface_config).
#
# HOW THE "AIR" WORKS
# -------------------
# There is no network of any kind between node processes. The medium is
# a spool directory of WAV files, one file per modem frame:
#   process_outgoing(raw RNS packet):
#       samples = nmm_modem.modem_encode(raw)
#       samples = tx_chain_test.apply_channel(samples, snr_db, 0, seed)
#       -> written atomically (<tx_dir>/fNNNNNN.wav) — this post-channel
#          audio IS the frame "on the air" for this hop.
#   receiver thread (polls <rx_dir>):
#       samples = read WAV; payload = nmm_modem.modem_decode(samples)
#       if payload is not None: owner.inbound(payload, self)
#       (owner is RNS.Transport; failed decodes are counted as lost
#        frames and the audio is archived under <rx_dir>/processed/)
# Each direction of each hop has its own spool dir, its own channel
# seed stream and its own stats file, so per-hop frame counts, retries
# and airtime are measured, not assumed.
#
# FRAGMENTATION: a single nmm_modem frame carries up to
# nmm_modem.MAX_PAYLOAD = 4096 bytes; Reticulum hands an interface at
# most one network packet (a few hundred bytes here — the test logs
# the maximum seen). One RNS packet therefore always fits in exactly
# one modem frame and NO link-layer fragmentation/reassembly is
# needed; frames-per-packet is 1.0 by construction and the stats
# verify the size headroom empirically.
#
# DUPLICATE SUPPRESSION (added 2026-10-20, DIGITAL LAB 3 debugging):
# frame_repeats puts up to 3 identical copies of every packet on the
# air per hop, and a transport node re-forwards each copy it receives,
# so the far interface can demodulate the SAME packet many times.
# A real interface never delivers one packet repeatedly, and RNS does
# not expect it: Resource.receive_part() resets the resource status
# to TRANSFERRING on every part packet it is handed, so a duplicate
# part arriving while Resource.assemble() runs (after it has set
# COMPLETE and sent the proof, before the LXMF delivery callback
# checks the status) silently reverts the status and LXMF drops the
# assembled message — the sender still sees DELIVERED, because the
# proof was already sent. Observed live in longmsg_mesh_test (500 B
# content, 2-part resource): delivery_resource_concluded fired with
# status=3 (TRANSFERRING) instead of 6 (COMPLETE) and no message was
# delivered. Fix: this interface injects each distinct packet payload
# at most once per DEDUP_WINDOW_S window (exact-payload SHA-256);
# later copies are counted as "rx_dup" and dropped. Loss protection
# is unaffected: suppression only starts AFTER a copy has decoded and
# been injected, so if every copy of a frame is lost, nothing was
# injected and nothing is suppressed.
DEDUP_WINDOW_S = 300.0

# LINK-LEVEL REPETITION (frame_repeats, default 1): at -10 dB the
# modem's per-frame loss for 200-250 B packets is roughly 1/3 (the
# 9/10 figure from DIGITAL LAB 1 was for 147 B packets), and a
# transport node will not re-forward a retransmitted copy of a
# packet it has already forwarded (RNS duplicate suppression), so
# end-to-end retransmission cannot recover a second-hop loss. The
# interface therefore optionally transmits every frame
# `frame_repeats` times, each copy through an INDEPENDENT channel
# seed. The receiving interface injects every copy that decodes;
# Reticulum's own packet-hash dedup discards the redundant copies.
# Every repetition is a separate stats "tx" event (field "repeat"),
# so the cost in airtime is fully accounted.
#
# BITRATE: self.bitrate is left at the Reticulum default guess
# (62500). RNS uses that field only for announce-rate heuristics; the
# modem's true rate is ~40 bit/s and all airtime accounting in the
# test is computed from actual frame sample counts, never from this
# field. (Built-in interfaces guess similarly — UDPInterface claims
# 10 Mbit/s on any link.)
#
# IFAC: no ifac_netname/ifac_netkey is configured, so Reticulum never
# sets interface.ifac_identity and packets cross this interface
# byte-identical to what Transport produced.

import hashlib
import json
import os
import sys
import threading
import time

import numpy as np


class ModemInterface(Interface):
    def __init__(self, owner, configuration):
        super().__init__()

        c = Interface.get_config_obj(configuration)
        self.owner = owner
        self.name = c["name"]
        self.tx_dir = c["tx_dir"]
        self.rx_dir = c["rx_dir"]
        self.stats_path = c["stats_path"]
        self.lab_dir = c["lab_dir"]
        self.seed_base = int(c["link_seed"])
        self.snr_db = float(c["snr_db"])
        self.frame_repeats = max(1, int(c.get("frame_repeats", 1)))

        self.IN = True
        self.OUT = False          # Reticulum sets OUT=True in post-init
        self.bitrate = 62500      # RNS default guess; see header note
        # Transport.preprocess_inbound drops packets by comparing
        # len(raw) > HW_MTU + ifac_size, so HW_MTU must be numeric
        # (the base class leaves it None). 1064 matches UDPInterface;
        # real RNS packets in this system are a few hundred bytes.
        self.HW_MTU = 1064
        self.online = False

        if self.lab_dir not in sys.path:
            sys.path.insert(0, self.lab_dir)
        import nmm_modem
        import tx_chain_test
        self._modem = nmm_modem
        self._channel = tx_chain_test

        os.makedirs(self.tx_dir, exist_ok=True)
        os.makedirs(self.rx_dir, exist_ok=True)
        self._processed_dir = os.path.join(self.rx_dir, "processed")
        os.makedirs(self._processed_dir, exist_ok=True)

        self._tx_lock = threading.Lock()
        self._stats_lock = threading.Lock()
        self._tx_seq = 0
        self._stop = False
        self._seen = set()
        self._injected = {}       # payload sha256 -> last inject time
        self.max_packet_seen = 0

        self._stat({"event": "interface_up", "name": self.name,
                    "snr_db": self.snr_db, "seed_base": self.seed_base})

        self._rx_thread = threading.Thread(target=self._rx_loop,
                                           daemon=True)
        self._rx_thread.start()
        self.online = True

    # -- statistics ---------------------------------------------------
    def _stat(self, ev):
        ev = dict(ev)
        ev["t"] = round(time.time(), 3)
        ev["iface"] = self.name
        try:
            with self._stats_lock:
                with open(self.stats_path, "a") as f:
                    f.write(json.dumps(ev) + "\n")
        except Exception:
            pass

    # -- transmit path --------------------------------------------------
    def process_outgoing(self, data):
        data = bytes(data)
        with self._tx_lock:
            self._tx_seq += 1
            seq = self._tx_seq
            self.max_packet_seen = max(self.max_packet_seen, len(data))
            enc = self._modem.modem_encode(data)
            # Same send level convention as modem_packet_test.py.
            x = enc.astype(np.float64)
            x = x * (6000.0 / np.sqrt(np.mean(x ** 2)))
            sha16 = hashlib.sha256(data).hexdigest()[:16]
            for rep in range(self.frame_repeats):
                # Independent channel realisation per repetition.
                seed = self.seed_base * 100000 + seq * 10 + rep
                rx, _meta = self._channel.apply_channel(x, self.snr_db,
                                                        0, seed)
                fname = f"f{seq:06d}_r{rep}.wav"
                tmp = os.path.join(self.tx_dir, f".tmp_{fname}")
                final = os.path.join(self.tx_dir, fname)
                self._channel.write_wav(tmp, rx)
                os.rename(tmp, final)  # atomic publish of complete frame
                self.txb += len(data)
                self._stat({"event": "tx", "seq": seq, "repeat": rep,
                            "pkt_len": len(data), "pkt_sha16": sha16,
                            "airtime_s": round(len(enc) / 12000.0, 2),
                            "seed": seed})

    # -- receive path ---------------------------------------------------
    def _rx_loop(self):
        while not self._stop:
            try:
                names = sorted(n for n in os.listdir(self.rx_dir)
                               if n.endswith(".wav"))
            except Exception:
                names = []
            for name in names:
                if name in self._seen:
                    continue
                path = os.path.join(self.rx_dir, name)
                try:
                    samples = self._channel.read_wav(path)
                except Exception:
                    continue          # unreadable yet; retry next pass
                self._seen.add(name)
                payload = self._modem.modem_decode(samples)
                if payload is not None:
                    phash = hashlib.sha256(payload).hexdigest()
                    now = time.time()
                    last = self._injected.get(phash)
                    if last is not None and now - last < DEDUP_WINDOW_S:
                        self._stat({"event": "rx_dup",
                                    "file": name,
                                    "pkt_len": len(payload),
                                    "pkt_sha16": phash[:16]})
                        try:
                            os.rename(path, os.path.join(
                                self._processed_dir, name))
                        except Exception:
                            pass
                        continue
                    self._injected[phash] = now
                    if len(self._injected) > 4096:
                        cutoff = now - DEDUP_WINDOW_S
                        self._injected = {h: t for h, t in
                                          self._injected.items()
                                          if t > cutoff}
                    self.rxb += len(payload)
                    self._stat({"event": "rx_ok",
                                "file": name,
                                "pkt_len": len(payload),
                                "pkt_sha16":
                                    hashlib.sha256(payload)
                                    .hexdigest()[:16]})
                    try:
                        self.owner.inbound(payload, self)
                    except Exception as e:
                        self._stat({"event": "rx_inbound_error",
                                    "file": name, "error": str(e)})
                else:
                    self._stat({"event": "rx_fail", "file": name})
                try:
                    os.rename(path, os.path.join(self._processed_dir,
                                                 name))
                except Exception:
                    pass
            time.sleep(0.25)

    def detach(self):
        self._stop = True
        self.online = False

    def __str__(self):
        return f"ModemInterface[{self.name}]"


interface_class = ModemInterface
