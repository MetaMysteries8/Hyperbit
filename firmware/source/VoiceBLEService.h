#pragma once
#include "MicroBit.h"
#include "MicroBitBLEService.h"

#define HYPERBIT_MAX_TTS_ADPCM 20000

enum HyperBitCharIndex {
    HB_MIC = 0,
    HB_SPEAKER = 1,
    HB_CONTROL = 2,
    HB_CHAR_COUNT = 3
};

enum HyperBitEvent {
    HB_EVT_PTT_START = 0x10,
    HB_EVT_PTT_END   = 0x11,
    HB_EVT_READY     = 0x12
};

enum HyperBitCommand {
    HB_CMD_TTS_START = 0x30,
    HB_CMD_TTS_END   = 0x31,
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
    bool ttsReady() const { return ttsReadyFlag; }
    void clearTtsReady() { ttsReadyFlag = false; }
    const uint8_t *ttsData() const;
    uint16_t ttsLength() const { return ttsLen; }
    uint8_t pcState() const { return pcStateValue; }
};
