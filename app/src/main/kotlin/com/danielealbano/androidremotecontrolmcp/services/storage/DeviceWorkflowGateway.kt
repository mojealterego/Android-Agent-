package com.danielealbano.androidremotecontrolmcp.services.storage

import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive

/** Ephemeral authority; never serialized as device data. */
data class WorkflowAccess(val stamp: String, val scopeLimited: Boolean = false)

/** Transport-neutral read-only core. A trusted entry point must bind identity before calling it. */
internal class DeviceWorkflowGateway(
    private val accessStamp: suspend (String) -> WorkflowAccess?,
    private val list: suspend (String, String, Int, Int) -> SearchPage,
) {
    private suspend fun stamp(location: String): WorkflowAccess {
        currentCoroutineContext().ensureActive()
        val result = accessStamp(location) ?: throw SecurityException("Storage workflow access denied")
        currentCoroutineContext().ensureActive()
        return result
    }

    suspend fun execute(plan: StorageWorkflow): WorkflowResult {
        val admitted = stamp(plan.locationId)
        suspend fun check(location: String) {
            if (stamp(location) != admitted) throw SecurityException("Storage workflow access changed")
        }
        val engine = StorageWorkflowEngine(FileSearchEngine { location, path, offset, limit ->
            check(location)
            val page = list(location, path, offset, limit)
            check(location)
            page
        })
        val result = engine.execute(plan)
        check(plan.locationId)
        // No-match in a restricted MediaStore view is not evidence of absence.
        if (!admitted.scopeLimited) return result
        return result.copy(complete = false, reasons = (result.reasons + "scoped_media_access").distinct(),
            steps = result.steps.map { step ->
                if (step.status == StepStatus.NO_MATCH_OBSERVED) step.copy(status = StepStatus.INDETERMINATE) else step
            })
    }
}
