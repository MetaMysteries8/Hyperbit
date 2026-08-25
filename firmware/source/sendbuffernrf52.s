.syntax unified

// MIT-licensed WS2812 timing routine adapted from Microsoft pxt-microbit.
// r0 = GPIO port base + 0x500
// r1 = pin number in low byte, brightness in bits 20+
// r2 = data pointer
// r3 = byte count

.section .data.neopixel_send_buffer_nrf52
.global neopixel_send_buffer_nrf52
.thumb
.type neopixel_send_buffer_nrf52, %function

neopixel_send_buffer_nrf52:
    push {r4,r5,r6,r7,lr}

    lsrs r7, r1, #20
    ands r1, #0xff
    movs r4, #1
    lsls r1, r4, r1

    mov r4, r2
    mov r5, r3
    mov r3, r0
    b .np_start

.np_nextbit:
    str r1, [r3, #0x8]
    movs r2, #8
    tst r6, r0
    it eq
    movseq r2, #3
.np_d1:
    subs r2, #1
    bne .np_d1

    str r1, [r3, #0xC]
    movs r2, #4
    tst r6, r0
    it eq
    movseq r2, #6

    lsrs r6, r6, #1
    beq .np_reload
    nop
    nop
    nop
.np_d0:
    subs r2, #1
    bne .np_d0
    b .np_nextbit

.np_reload:
    subs r2, #2
.np_d2:
    subs r2, #1
    bne .np_d2

    adds r4, #1
    subs r5, #1
    ble .np_stop

.np_start:
    movs r6, #0x80
    ldrb r0, [r4, #0]
    muls r0, r7
    lsrs r0, r0, #8
    str r1, [r3, #0xC]
    b .np_nextbit

.np_stop:
    str r1, [r3, #0xC]
    pop {r4,r5,r6,r7,pc}
