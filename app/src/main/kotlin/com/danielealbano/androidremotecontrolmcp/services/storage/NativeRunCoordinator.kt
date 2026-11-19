package com.danielealbano.androidremotecontrolmcp.services.storage

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.withContext
import java.io.IOException
import java.nio.ByteBuffer
import java.nio.channels.FileChannel
import java.nio.file.Files
import java.nio.file.LinkOption
import java.nio.file.Path
import java.nio.file.StandardCopyOption
import java.nio.file.StandardOpenOption

internal enum class NativeRunState { IDLE, RUNNING, COMPLETED, FAILED, CANCELLED, INTERRUPTED }
internal class NativeRunBusy : IllegalStateException("Native workflow already running")

/** Latest state only; no filenames, query, identity, tokens or results. Requires app-private parent. */
internal class NativeRunJournal(private val path: Path) {
    fun read(): NativeRunState {
        if (Files.notExists(path, LinkOption.NOFOLLOW_LINKS)) return NativeRunState.IDLE
        try {
            if (!Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS)) throw IOException("Invalid workflow journal")
            FileChannel.open(path, StandardOpenOption.READ, LinkOption.NOFOLLOW_LINKS).use { channel ->
                if (!Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS) || channel.size() !in 1..32) throw IOException("Invalid workflow journal")
                val buffer = ByteBuffer.allocate(33)
                while (buffer.hasRemaining() && channel.read(buffer) > 0) { /* bounded regular-file read */ }
                val text = String(buffer.array(), 0, buffer.position(), Charsets.US_ASCII)
                return NativeRunState.entries.firstOrNull { text == "${it.name}\n" }
                    ?: throw IOException("Invalid workflow journal")
            }
        } catch (e: IOException) { throw IOException("Workflow journal unavailable", e) }
    }

    fun write(state: NativeRunState) {
        val temp = Files.createTempFile(path.parent, ".omega-state-", ".tmp")
        try {
            FileChannel.open(temp, StandardOpenOption.WRITE).use { channel ->
                val bytes = ByteBuffer.wrap("${state.name}\n".toByteArray(Charsets.US_ASCII))
                while (bytes.hasRemaining()) channel.write(bytes)
                channel.force(true)
            }
            Files.move(temp, path, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
        } finally { Files.deleteIfExists(temp) }
    }
}

/** One process-wide coordinator. Never automatically resumes or replays an interrupted job. */
internal class NativeRunCoordinator(private val journal: NativeRunJournal) {
    private val lock = Mutex()
    suspend fun recover(): NativeRunState {
        if (!lock.tryLock()) throw NativeRunBusy()
        return try { recoverLocked() } finally { lock.unlock() }
    }
    private fun recoverLocked(): NativeRunState {
        val previous = journal.read()
        return if (previous == NativeRunState.RUNNING) {
            journal.write(NativeRunState.INTERRUPTED)
            NativeRunState.INTERRUPTED
        } else previous
    }
    suspend fun <T> run(action: suspend () -> T): T {
        if (!lock.tryLock()) throw NativeRunBusy()
        try {
            recoverLocked()
            currentCoroutineContext().ensureActive()
            journal.write(NativeRunState.RUNNING)
            try {
                val result = action()
                currentCoroutineContext().ensureActive()
                journal.write(NativeRunState.COMPLETED)
                return result
            } catch (e: CancellationException) {
                withContext(NonCancellable) {
                    try { journal.write(NativeRunState.CANCELLED) } catch (failure: IOException) { e.addSuppressed(failure) }
                }
                throw e
            } catch (e: Exception) {
                try { journal.write(NativeRunState.FAILED) } catch (failure: IOException) { e.addSuppressed(failure) }
                throw e
            }
        } finally { lock.unlock() }
    }
}
