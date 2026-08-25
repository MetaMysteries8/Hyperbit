#pragma once
#include "MicroBit.h"
#include "MicroBitBLEService.h"

#define HYPERBIT_MAX_TTS_ADPCM 4096

enum HyperBitCharIndex {
    HB_MIC = 0,
    HB_SPEAKER = 1,
    HB_CONTROL = 2,
    HB_CHAR_COUNT = 3
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

class VoiceBLEService : public codal::MicroBitBLEService {
    uint8_t micValue[20];
    uint8_t speakerValue[20];
    uint8_t controlValue[20];
    codal::MicroBitBLEChar chars[HB_CHAR_COUNT];

    bool ttsReceiving;
    volatile bool ttsReadyFlag;
    uint16_t ttsLen;
    uint16_t ttsExpectedLen;
    bool ttsFirstSegmentFlag;
    uint8_t expectedSpeakerSeq;
    uint8_t pcStateValue;

protected:
    virtual void onDataWritten(const microbit_ble_evt_write_t *params);

public:
    VoiceBLEService();

    virtual int characteristicCount() { return HB_CHAR_COUNT; }
    virtual codal::MicroBitBLEChar *characteristicPtr(int idx) { return &chars[idx]; }

    bool sendControl(uint8_t code, uint8_t a=0, uint8_t b=0, uint8_t c=0);
    bool sendMic(uint8_t seq, const uint8_t *data, int len);

    // A raw BLE connection is not enough: Windows must finish discovering the
    // service and subscribe to both notification characteristics. This is used
    // by the firmware to detect and evict half-open WinRT/GATT sessions.
    bool notificationsReady() {
        return getConnected() &&
               notifyChrValueEnabled(HB_MIC) &&
               notifyChrValueEnabled(HB_CONTROL);
    }

    bool ttsReady() const { return ttsReadyFlag; }
    void clearTtsReady() { ttsReadyFlag = false; }
    void abortTts();

    const uint8_t *ttsData() const;
    uint16_t ttsLength() const { return ttsLen; }
    bool ttsFirstSegment() const { return ttsFirstSegmentFlag; }
    uint8_t pcState() const { return pcStateValue; }
};
