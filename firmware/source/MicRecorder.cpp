#include "MicRecorder.h"

using namespace codal;

static uint8_t MIC_RING[HYPERBIT_MIC_RING_BYTES];

MicRecorder::MicRecorder(DataSource &source) :
    upstream(source),
    recording(false),
    overflow(false),
    head(0),
    tail(0),
    sampleCount(0),
    halfNibble(false),
    pendingByte(0)
{
    source.connect(*this);

    // Do NOT keep the microphone pipeline permanently requested.
    // On micro:bit V2, DATASTREAM_WANTED propagates all the way to the
    // NRF52 ADC channel and powers/activates the microphone. Push-to-talk
    // owns this demand explicitly in start()/stop().
    source.dataWanted(DATASTREAM_NOT_WANTED);
}

void MicRecorder::start() {
    recording = false;
    head = 0;
    tail = 0;
    sampleCount = 0;
    overflow = false;
    halfNibble = false;
    pendingByte = 0;
    adpcm.reset();

    // Mark ourselves ready before requesting data, because requesting the
    // stream can activate the ADC immediately.
    recording = true;
    upstream.dataWanted(DATASTREAM_WANTED);
}

void MicRecorder::stop() {
    recording = false;

    // Release microphone demand first. This propagates through the splitter
    // and causes the NRF52 ADC channel to be released/disabled when no other
    // consumer wants microphone samples.
    upstream.dataWanted(DATASTREAM_NOT_WANTED);

    if (halfNibble) {
        if (!pushByte(pendingByte))
            overflow = true;
        halfNibble = false;
    }
}

bool MicRecorder::pushByte(uint8_t value) {
    uint16_t next = (head + 1) % HYPERBIT_MIC_RING_BYTES;
    if (next == tail)
        return false;

    MIC_RING[head] = value;
    head = next;
    return true;
}

int MicRecorder::available() const {
    uint16_t h = head;
    uint16_t t = tail;
    if (h >= t)
        return h - t;
    return HYPERBIT_MIC_RING_BYTES - t + h;
}

int MicRecorder::read(uint8_t *out, int maxLen) {
    if (!out || maxLen <= 0)
        return 0;

    int count = 0;
    while (count < maxLen && tail != head) {
        out[count++] = MIC_RING[tail];
        tail = (tail + 1) % HYPERBIT_MIC_RING_BYTES;
    }
    return count;
}

int MicRecorder::pullRequest() {
    ManagedBuffer b = upstream.pull();
    if (!recording)
        return DEVICE_OK;

    for (int i = 0; i < b.length(); ++i) {
        int8_t s8 = (int8_t)b[i];
        int16_t sample = ((int16_t)s8) << 8;
        uint8_t nibble = adpcm.encode(sample);

        if (!halfNibble) {
            pendingByte = nibble & 0x0F;
            halfNibble = true;
        } else {
            if (!pushByte(pendingByte | ((nibble & 0x0F) << 4)))
                overflow = true;
            halfNibble = false;
        }

        if (sampleCount < 0x7FFFFF)
            ++sampleCount;
    }

    return DEVICE_OK;
}
