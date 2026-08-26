#pragma once
#include "MicroBit.h"
#include "MicroBitBLEService.h"

// Keep TTS chunks deliberately small. CODAL's softdevice linker script expands
// its .heap section to the RAM limit, so the generic linker RAM percentage is
// not a free-heap measurement. A smaller segment still increases real dynamic
// heap capacity and reduces runtime buffering pressure.
#define HYPERBIT_MAX_TTS_ADPCM 512
#define HYPERBIT_NUS_AUDIO_PAYLOAD 17
#define HYPERBIT_PROTOCOL_VERSION 2

// Protocol v2 stays wire-compatible while the firmware revision identifies the
// minimum implementation required by the PC. READY reports both revision and
// capabilities so a stale HEX is rejected instead of being debugged by accident.
#define HYPERBIT_FIRMWARE_REVISION 4
#define HYPERBIT_CAP_CONNECTION_ISOLATION 0x01
#define HYPERBIT_CAP_SAFE_RAINBOW_PWM      0x02
#define HYPERBIT_CAP_SEGMENTED_TTS         0x04
#define HYPERBIT_CAP_BUFFERED_HVN          0x08
#define HYPERBIT_CAPABILITIES (HYPERBIT_CAP_CONNECTION_ISOLATION | HYPERBIT_CAP_SAFE_RAINBOW_PWM | HYPERBIT_CAP_SEGMENTED_TTS | HYPERBIT_CAP_BUFFERED_HVN)

enum HyperBitCharIndex {
    HB_NUS_TX = 0,
    HB_NUS_RX = 1,
    HB_CHAR_COUNT = 2
};

enum HyperBitFrameType {
    HB_FRAME_CONTROL = 0xA0,
    HB_FRAME_MIC     = 0xA1,
    HB_FRAME_TTS     = 0xA2,
    HB_FRAME_HELLO   = 0xA3
};

enum HyperBitEvent {
    HB_EVT_PTT_START        = 0x10,
    HB_EVT_PTT_END          = 0x11,
    HB_EVT_READY            = 0x12,
    HB_EVT_CANCEL           = 0x13,
    HB_EVT_REPLAY           = 0x14,
    HB_EVT_MUTE_CHANGED     = 0x15,
    HB_EVT_TTS_SEGMENT_DONE = 0x16,
    HB_EVT_WUKONG_STATUS    = 0x17
};

enum HyperBitCommand {
    HB_CMD_TTS_START = 0x30,
    HB_CMD_TTS_END   = 0x31,
    HB_CMD_TTS_ABORT = 0x32,
    HB_CMD_SET_STATE = 0x40
};

// HyperBit uses the standard Nordic UART Service UUID layout:
//   service 6e400001-b5a3-f393-e0a9-e50e24dcca9e
//   RX      6e400002-b5a3-f393-e0a9-e50e24dcca9e (PC -> device)
//   TX      6e400003-b5a3-f393-e0a9-e50e24dcca9e (device -> PC)
//
// We keep a tiny framed protocol on top because audio needs packet boundaries
// and notification throughput; the old HyperBit-specific 7f9a service is gone.
class VoiceBLEService : public codal::MicroBitBLEService {
    uint8_t txValue[20];
    uint8_t rxValue[20];
    codal::MicroBitBLEChar chars[HB_CHAR_COUNT];

    volatile bool sessionReadyFlag;
    bool ttsReceiving;
    volatile bool ttsReadyFlag;
    uint16_t ttsLen;
    uint16_t ttsExpectedLen;
    bool ttsFirstSegmentFlag;
    uint8_t expectedSpeakerSeq;
    uint8_t pcStateValue;

protected:
    virtual void onConnect(const microbit_ble_evt_t *p_ble_evt);
    virtual void onDisconnect(const microbit_ble_evt_t *p_ble_evt);
    virtual void onDataWritten(const microbit_ble_evt_write_t *params);

public:
    VoiceBLEService();

    virtual int characteristicCount() { return HB_CHAR_COUNT; }
    virtual codal::MicroBitBLEChar *characteristicPtr(int idx) { return &chars[idx]; }

    bool sendControl(uint8_t code, uint8_t a=0, uint8_t b=0, uint8_t c=0);
    bool sendMic(uint8_t seq, const uint8_t *data, int len);

    // HELLO is accepted only after the PC has enabled TX notifications. Checking
    // the CCCD here is safe because HELLO arrives after Windows GATT discovery;
    // we intentionally never poll it during the fragile discovery window.
    bool notificationsReady() {
        return getConnected() && sessionReadyFlag && notifyChrValueEnabled(HB_NUS_TX);
    }
    void resetSession();

    bool ttsReady() const { return ttsReadyFlag; }
    void clearTtsReady() { ttsReadyFlag = false; }
    void abortTts();

    const uint8_t *ttsData() const;
    uint16_t ttsLength() const { return ttsLen; }
    bool ttsFirstSegment() const { return ttsFirstSegmentFlag; }
    uint8_t pcState() const { return pcStateValue; }
};
