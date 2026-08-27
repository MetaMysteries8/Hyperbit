#include "VoiceBLEService.h"

using namespace codal;

static uint8_t TTS_BUFFER[HYPERBIT_MAX_TTS_ADPCM];

static_assert(HB_NUS_TX == MicroBitUARTService::mbbs_cIdxTX,
              "HyperBit TX index must match CODAL UART TX index");
static_assert(HB_NUS_RX == MicroBitUARTService::mbbs_cIdxRX,
              "HyperBit RX index must match CODAL UART RX index");
static_assert(HB_CHAR_COUNT == MicroBitUARTService::mbbs_cIdxCOUNT,
              "HyperBit characteristic count must match CODAL UART service");

VoiceBLEService::VoiceBLEService() :
    MicroBitUARTService(*MicroBitBLEManager::getInstance()),
    sessionReadyFlag(false),
    ttsReceiving(false),
    ttsReadyFlag(false),
    ttsLen(0),
    ttsExpectedLen(0),
    ttsFirstSegmentFlag(false),
    expectedSpeakerSeq(0),
    pcStateValue(0)
{
    // r6 intentionally does not call RegisterBaseUUID(), CreateService() or
    // CreateCharacteristic(). The locked CODAL MicroBitUARTService constructor
    // owns the complete NUS GATT registration path.
}

const uint8_t *VoiceBLEService::ttsData() const {
    return TTS_BUFFER;
}

void VoiceBLEService::resetSession() {
    sessionReadyFlag = false;
    pcStateValue = 0;
    abortTts();
}

void VoiceBLEService::onConnect(const microbit_ble_evt_t *p_ble_evt) {
    (void)p_ble_evt;
    // Never inherit application state across a fast reconnect.
    resetSession();
}

void VoiceBLEService::onDisconnect(const microbit_ble_evt_t *p_ble_evt) {
    (void)p_ble_evt;
    // Reset immediately in BLE event context instead of waiting for main-loop
    // polling to notice the disconnect.
    resetSession();
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
    if (!getConnected() || !sessionReadyFlag || !notifyChrValueEnabled(HB_NUS_TX))
        return false;

    uint8_t frame[5] = {HB_FRAME_CONTROL, code, a, b, c};
    return notifyChrValue(HB_NUS_TX, frame, sizeof(frame));
}

bool VoiceBLEService::sendMic(uint8_t seq, const uint8_t *data, int len) {
    if (!getConnected() || !sessionReadyFlag || !notifyChrValueEnabled(HB_NUS_TX) || !data || len < 0)
        return false;

    if (len > HYPERBIT_NUS_AUDIO_PAYLOAD)
        len = HYPERBIT_NUS_AUDIO_PAYLOAD;

    uint8_t frame[20];
    frame[0] = HB_FRAME_MIC;
    frame[1] = seq;
    frame[2] = (uint8_t)len;
    for (int i = 0; i < len; ++i)
        frame[i + 3] = data[i];

    return notifyChrValue(HB_NUS_TX, frame, len + 3);
}

void VoiceBLEService::onDataWritten(const microbit_ble_evt_write_t *params) {
    if (params->handle != valueHandle(HB_NUS_RX) || params->len < 1)
        return;

    const uint8_t *data = params->data;
    const uint16_t len = params->len;
    const uint8_t frameType = data[0];

    if (frameType == HB_FRAME_HELLO) {
        // HELLO is the first application write. The PC must already have enabled
        // TX notifications, otherwise READY could never be delivered. This also
        // makes an accidental write from a generic NUS client insufficient to
        // enter the interactive state.
        sessionReadyFlag = (
            len >= 2 &&
            data[1] == HYPERBIT_PROTOCOL_VERSION &&
            notifyChrValueEnabled(HB_NUS_TX)
        );
        if (!sessionReadyFlag)
            abortTts();
        return;
    }

    // Ignore application data until the PC has completed the explicit HELLO
    // handshake. A raw BLE connection alone is not a HyperBit session.
    if (!sessionReadyFlag || !notifyChrValueEnabled(HB_NUS_TX))
        return;

    if (frameType == HB_FRAME_TTS) {
        if (!ttsReceiving || len < 3)
            return;

        const uint8_t seq = data[1];
        int payload = data[2];
        if (payload > HYPERBIT_NUS_AUDIO_PAYLOAD)
            payload = HYPERBIT_NUS_AUDIO_PAYLOAD;
        if (payload > (int)len - 3)
            payload = (int)len - 3;

        if (seq != expectedSpeakerSeq) {
            abortTts();
            sendControl(HB_EVT_TTS_SEGMENT_DONE, 0);
            return;
        }
        expectedSpeakerSeq = (uint8_t)(seq + 1);

        int room = HYPERBIT_MAX_TTS_ADPCM - ttsLen;
        if (payload > room)
            payload = room;

        for (int i = 0; i < payload; ++i)
            TTS_BUFFER[ttsLen++] = data[i + 3];

        return;
    }

    if (frameType != HB_FRAME_CONTROL || len < 2)
        return;

    const uint8_t code = data[1];

    if (code == HB_CMD_TTS_START) {
        abortTts();
        ttsReceiving = true;
        if (len >= 4)
            ttsExpectedLen = data[2] | (data[3] << 8);
        if (ttsExpectedLen > HYPERBIT_MAX_TTS_ADPCM) {
            abortTts();
            sendControl(HB_EVT_TTS_SEGMENT_DONE, 0);
            return;
        }
        if (len >= 5)
            ttsFirstSegmentFlag = (data[4] & 0x01) != 0;
        return;
    }

    if (code == HB_CMD_TTS_END) {
        // An earlier sequence/length fault calls abortTts(), which clears the
        // lengths. The PC may already have queued TTS_END, so never let that
        // stale end frame turn an aborted zero-length receive into success.
        if (!ttsReceiving)
            return;

        ttsReceiving = false;
        if (ttsLen == ttsExpectedLen) {
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

    if (code == HB_CMD_SET_STATE && len >= 3) {
        pcStateValue = data[2];
        return;
    }
}
