#include "VoiceBLEService.h"

using namespace codal;

static uint8_t TTS_BUFFER[HYPERBIT_MAX_TTS_ADPCM];

// RegisterBaseUUID reverses this array internally for the Nordic SoftDevice,
// so keep it here in normal human UUID byte order.
static const uint8_t HB_BASE_UUID[16] = {
    0x7f,0x9a,0x00,0x00,0x4c,0x1d,0x4b,0x8f,
    0x9a,0x31,0xc6,0x2d,0x5e,0x8b,0x1f,0x70
};

static const uint16_t HB_SERVICE_UUID = 0x0001;
static const uint16_t HB_CHAR_UUID[HB_CHAR_COUNT] = {0x0002, 0x0003, 0x0004};

VoiceBLEService::VoiceBLEService() :
    ttsReceiving(false),
    ttsReadyFlag(false),
    ttsLen(0),
    ttsExpectedLen(0),
    ttsFirstSegmentFlag(false),
    expectedSpeakerSeq(0),
    pcStateValue(0)
{
    RegisterBaseUUID(HB_BASE_UUID);
    CreateService(HB_SERVICE_UUID);
    CreateCharacteristic(HB_MIC, HB_CHAR_UUID[HB_MIC], micValue, 0, sizeof(micValue), microbit_propNOTIFY);
    CreateCharacteristic(HB_SPEAKER, HB_CHAR_UUID[HB_SPEAKER], speakerValue, 0, sizeof(speakerValue), microbit_propWRITE | microbit_propWRITE_WITHOUT);
    CreateCharacteristic(HB_CONTROL, HB_CHAR_UUID[HB_CONTROL], controlValue, 0, sizeof(controlValue), microbit_propWRITE | microbit_propWRITE_WITHOUT | microbit_propNOTIFY);
}

const uint8_t *VoiceBLEService::ttsData() const {
    return TTS_BUFFER;
}

void VoiceBLEService::abortTts() {
    ttsReceiving = false;
    ttsReadyFlag = false;
    ttsLen = 0;
    ttsExpectedLen = 0;
    ttsFirstSegmentFlag = false;
    expectedSpeakerSeq = 0;
}

bool VoiceBLEService::sendControl(uint8_t code, uint8_t a, uint8_t b, uint8_t c) {
    uint8_t msg[4] = {code, a, b, c};
    if (!getConnected() || !notifyChrValueEnabled(HB_CONTROL))
        return false;
    return notifyChrValue(HB_CONTROL, msg, sizeof(msg));
}

bool VoiceBLEService::sendMic(uint8_t seq, const uint8_t *data, int len) {
    if (!getConnected() || !notifyChrValueEnabled(HB_MIC))
        return false;
    if (len < 0)
        return false;
    if (len > 19)
        len = 19;

    uint8_t packet[20];
    packet[0] = seq;
    for (int i = 0; i < len; ++i)
        packet[i + 1] = data[i];

    return notifyChrValue(HB_MIC, packet, len + 1);
}

void VoiceBLEService::onDataWritten(const microbit_ble_evt_write_t *params) {
    if (params->handle == valueHandle(HB_SPEAKER)) {
        if (!ttsReceiving || params->len < 2)
            return;

        uint8_t seq = params->data[0];
        expectedSpeakerSeq = seq + 1;

        int payload = params->len - 1;
        int room = HYPERBIT_MAX_TTS_ADPCM - ttsLen;
        if (payload > room)
            payload = room;

        for (int i = 0; i < payload; ++i)
            TTS_BUFFER[ttsLen++] = params->data[i + 1];

        return;
    }

    if (params->handle == valueHandle(HB_CONTROL) && params->len >= 1) {
        uint8_t code = params->data[0];

        if (code == HB_CMD_TTS_START) {
            abortTts();
            ttsReceiving = true;
            if (params->len >= 3)
                ttsExpectedLen = params->data[1] | (params->data[2] << 8);
            if (params->len >= 4)
                ttsFirstSegmentFlag = (params->data[3] & 0x01) != 0;
            return;
        }

        if (code == HB_CMD_TTS_END) {
            ttsReceiving = false;
            if (ttsExpectedLen == 0 || ttsLen == ttsExpectedLen) {
                ttsReadyFlag = true;
            } else {
                abortTts();
                sendControl(HB_EVT_TTS_SEGMENT_DONE, 0);
            }
            return;
        }

        if (code == HB_CMD_TTS_ABORT) {
            abortTts();
            return;
        }

        if (code == HB_CMD_SET_STATE && params->len >= 2) {
            pcStateValue = params->data[1];
            return;
        }
    }
}
