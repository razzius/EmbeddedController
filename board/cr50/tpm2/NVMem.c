/* Copyright 2015 The Chromium OS Authors. All rights reserved.
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file.
 *
 * The function prototypes were extracted from the TCG Published
 * Trusted Platform Module Library
 * Part 4: Supporting Routines
 * Family "2.0"
 * Level 00 Revision 01.16
 * October 30, 2014
 */

#include <string.h>

#include "PlatformData.h"
#include "TpmError.h"
#include "assert.h"

/* Local state */
static unsigned char s_NV[NV_MEMORY_SIZE];
static BOOL s_NvIsAvailable;
static BOOL s_NV_unrecoverable;
static BOOL s_NV_recoverable;

/*
 * This function is used by the simulator to set the error flags in the NV
 * subsystem to simulate an error in the NV loading process.
 */
void _plat__NvErrors(BOOL recoverable, BOOL unrecoverable)
{
	s_NV_unrecoverable = unrecoverable;
	s_NV_recoverable = recoverable;
}

/*
 * This function should retrieve and verify the integrity of the saved context.
 * On success, the NV content has been copied into local RAM for fast access.
 *
 * The recovery from an integrity failure depends on where the error occurred.
 * It it was in the state that is discarded by TPM Reset, then the error is
 * recoverable if the TPM is reset. Otherwise, the TPM must go into failure
 * mode.
 *
 *     Return Value                      Meaning
 *
 *     0                                 if success
 *     >0                                if receive recoverable error
 *     <0                                if unrecoverable error
 */
int _plat__NVEnable(void *platParameter)
{
	s_NV_unrecoverable = FALSE;
	s_NV_recoverable = FALSE;

	if (s_NV_unrecoverable)
		return -1;
	return s_NV_recoverable;
}

void _plat__NVDisable(void)
{
	/* nothing yet */
}

/*
 * Check if NV is available
 *
 *      Return Value                      Meaning
 *
 *      0                                 NV is available
 *      1                                 NV not available due to write failure
 *      2                                 NV not available due to rate limit
 */
int _plat__IsNvAvailable(void)
{
	if (!s_NvIsAvailable)
		return 1;

	return 0;
}

/*
 * Read a chunk of NV memory
 */
void _plat__NvMemoryRead(unsigned int startOffset,
				    unsigned int size,
				    void *data)
{
	assert(startOffset + size <= NV_MEMORY_SIZE);
	/* Copy the data from the NV image */
	memcpy(data, &s_NV[startOffset], size);
	return;
}

/*
 * This function tests to see if the NV is different from the test value.
 * Returns true if different, false if not.
 */
BOOL
_plat__NvIsDifferent(unsigned int startOffset,
		     unsigned int size,
		     void *data)
{
	/* Do we need a safe memcmp here? */
	return (memcmp(&s_NV[startOffset], data, size) != 0);
}

/*
 * This function is used to update NV memory. The write is to a memory copy of
 * NV. At the end of the current command, any changes are written to the actual
 * NV memory.
 */
void _plat__NvMemoryWrite(unsigned int startOffset,
			  unsigned int size,
			  void *data)
{
	assert(startOffset + size <= NV_MEMORY_SIZE);
	/* Copy the data to the NV image */
	memcpy(&s_NV[startOffset], data, size);
}

/*
 *      Function: Move a chunk of NV memory from source to destination,
 *      handling overlap correctly.
 */
void _plat__NvMemoryMove(unsigned int sourceOffset,
				    unsigned int destOffset,
				    unsigned int size)
{
	assert(sourceOffset + size <= NV_MEMORY_SIZE);
	assert(destOffset + size <= NV_MEMORY_SIZE);
	/* Move data in RAM */
	memmove(&s_NV[destOffset], &s_NV[sourceOffset], size);
	return;
}

/*
 * Commit the local RAM copy to NV storage.
 *
 *      Return Value                      Meaning
 *
 *      0                                 NV write success
 *      non-0                             NV write fail
 */
int _plat__NvCommit(void)
{
	return 0;
}

/*
 * Set the current NV state to available. This function is for testing purpose
 * only. It is not part of the platform NV logic
 */
void _plat__SetNvAvail(void)
{
	s_NvIsAvailable = TRUE;
	return;
}

/*
 * Set the current NV state to unavailable. This function is for testing
 * purpose only. It is not part of the platform NV logic
 */
void _plat__ClearNvAvail(void)
{
	s_NvIsAvailable = FALSE;
	return;
}
