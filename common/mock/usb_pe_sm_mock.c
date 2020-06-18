/* Copyright 2020 The Chromium OS Authors. All rights reserved.
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file.
 */

/* Mock USB PE state machine */

#include "common.h"
#include "console.h"
#include "usb_pe_sm.h"
#include "mock/usb_pe_sm_mock.h"
#include "memory.h"

#ifndef CONFIG_COMMON_RUNTIME
#define cprints(format, args...)
#endif


struct mock_pe_port_t mock_pe_port[CONFIG_USB_PD_PORT_MAX_COUNT];


void pe_report_error(int port, enum pe_error e, enum tcpm_transmit_type type)
{
	mock_pe_port[port].mock_pe_error = e;
	mock_pe_port[port].sop = type;
}

void pe_got_hard_reset(int port)
{
	mock_pe_port[port].mock_pe_got_hard_reset = 1;
}

void pe_message_received(int port)
{
	mock_pe_port[port].mock_pe_message_received = 1;
}

void pe_message_sent(int port)
{
	mock_pe_port[port].mock_pe_message_sent = 1;
}

void pe_hard_reset_sent(int port)
{
	mock_pe_port[port].mock_pe_hard_reset_sent = 1;
}

void pe_got_soft_reset(int port)
{
	mock_pe_port[port].mock_got_soft_reset = 1;
}

bool pe_in_local_ams(int port)
{
	/* We will probably want to change this in the future */
	return false;
}

