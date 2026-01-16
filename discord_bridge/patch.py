import logging
from discord.ext.voice_recv.opus import PacketDecoder

log = logging.getLogger(__name__)


def apply_fault_tolerance():
    """Patches PacketDecoder to tolerate corrupted packets."""
    _original_decode = PacketDecoder._decode_packet

    def safe_decode(self, packet):
        try:
            return _original_decode(self, packet)
        except Exception:
            # Return silence (empty bytes) on corruption
            return packet, b""

    PacketDecoder._decode_packet = safe_decode
    log.info("🩹 Opus Fault Tolerance Patch Applied")
