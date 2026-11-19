package com.danielealbano.androidremotecontrolmcp.services.storage

import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.nio.ByteBuffer
import java.nio.CharBuffer
import java.nio.charset.CodingErrorAction
import java.security.MessageDigest
import java.util.UUID

/** Backend is a trusted, owner-authorized document provider; create must create a new document. */
internal interface SafRevisionBackend {
    suspend fun access(location: String): String?
    suspend fun lookup(location: String, grant: String, name: String): String?
    suspend fun read(location: String, grant: String, id: String): ByteArray
    suspend fun create(location: String, grant: String, name: String): String
    suspend fun writeFresh(location: String, grant: String, id: String, bytes: ByteArray)
}

internal data class SafRevisionPreview(val token: String, val source: String, val destination: String, val before: String, val after: String, val beforeSha256: String, val afterSha256: String)
internal data class SafRevisionResult(val destination: String, val sha256: String)

/** One ephemeral owner-confirmed copy-on-write plan; never overwrite, delete or retry a provider write. */
internal class SafRevisionEngine(private val backend: SafRevisionBackend, private val journal: SafRevisionJournal? = null, private val now: () -> Long = { System.nanoTime() / 1_000_000L }) {
    private data class Plan(val view: SafRevisionPreview, val location: String, val grant: String, val sourceId: String, val original: ByteArray, val replacement: ByteArray, val expires: Long)
    private val lock = Mutex()
    private var plan: Plan? = null

    private fun text(bytes: ByteArray): String {
        require(bytes.size <= MAX_BYTES) { "Text exceeds limit" }
        return Charsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes)).toString().also { require('\u0000' !in it) }
    }
    private fun encode(value: String): ByteArray {
        require(value.length <= MAX_BYTES && '\u0000' !in value) { "Text exceeds limit" }
        val b = Charsets.UTF_8.newEncoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT).encode(CharBuffer.wrap(value))
        require(b.remaining() <= MAX_BYTES) { "Text exceeds limit" }
        return ByteArray(b.remaining()).also { b.get(it) }
    }
    private fun digest(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it.toInt() and 255) }
    private suspend fun access(location: String): String {
        currentCoroutineContext().ensureActive()
        return backend.access(location) ?: throw SecurityException("SAF revision denied")
    }
    private suspend fun checkGrant(location: String, expected: String) {
        if (access(location) != expected) throw SecurityException("SAF grant changed")
    }
    suspend fun receipt(): SafReceipt? = lock.withLock { journal?.read() }
    suspend fun acknowledge(destination: String) = lock.withLock {
        val current = journal?.read() ?: error("No revision receipt")
        check(current.state == SafReceiptState.PENDING && current.destination == destination)
        journal.write(current.copy(state = SafReceiptState.ACKNOWLEDGED))
    }
    suspend fun discard() = lock.withLock { plan = null }
    suspend fun preview(location: String, source: String, replacement: String): SafRevisionPreview = lock.withLock {
        plan = null
        check(journal?.read()?.state != SafReceiptState.PENDING) { "Previous uncertain revision requires inspection" }
        require(location.isNotBlank() && location.length <= 2048)
        require(source.matches(Regex("[\\p{L}\\p{N}][\\p{L}\\p{N} _.-]{0,119}\\.(txt|md|csv|json|log)", RegexOption.IGNORE_CASE))) { "Only an explicit root text filename is supported" }
        val after = encode(replacement)
        val grant = access(location)
        val id = backend.lookup(location, grant, source) ?: error("Source not found")
        checkGrant(location, grant)
        val before = backend.read(location, grant, id).copyOf()
        val beforeText = text(before)
        require(!before.contentEquals(after)) { "No change" }
        checkGrant(location, grant)
        val token = UUID.randomUUID().toString()
        val destination = "omega-$token.txt"
        check(backend.lookup(location, grant, destination) == null) { "Destination exists" }
        checkGrant(location, grant)
        val view = SafRevisionPreview(token, source, destination, beforeText, replacement, digest(before), digest(after))
        plan = Plan(view, location, grant, id, before, after, now() + 120_000)
        view
    }
    suspend fun apply(token: String): SafRevisionResult = lock.withLock {
        val p = plan ?: error("No preview")
        check(token == p.view.token && now() < p.expires) { "Approval invalid or expired" }
        // Consume before any effect, including failed or uncertain attempts.
        plan = null
        suspend fun checkSource() {
            checkGrant(p.location, p.grant)
            check(backend.lookup(p.location, p.grant, p.view.source) == p.sourceId) { "Source identity changed" }
            check(backend.read(p.location, p.grant, p.sourceId).contentEquals(p.original)) { "Source content changed" }
            checkGrant(p.location, p.grant)
        }
        checkSource()
        check(backend.lookup(p.location, p.grant, p.view.destination) == null) { "Destination exists" }
        checkGrant(p.location, p.grant)
        check(journal?.read()?.state != SafReceiptState.PENDING) { "Previous uncertain revision requires inspection" }
        journal?.write(SafReceipt(p.view.destination, SafReceiptState.PENDING))
        currentCoroutineContext().ensureActive()
        val fresh = backend.create(p.location, p.grant, p.view.destination)
        check(fresh != p.sourceId) { "Provider returned source identity" }
        checkGrant(p.location, p.grant)
        check(backend.lookup(p.location, p.grant, p.view.destination) == fresh && backend.read(p.location, p.grant, fresh).isEmpty()) { "New document not confirmed empty" }
        checkSource()
        checkGrant(p.location, p.grant)
        backend.writeFresh(p.location, p.grant, fresh, p.replacement.copyOf())
        checkGrant(p.location, p.grant)
        check(backend.lookup(p.location, p.grant, p.view.destination) == fresh && backend.read(p.location, p.grant, fresh).contentEquals(p.replacement)) { "Output verification failed" }
        checkSource()
        journal?.write(SafReceipt(p.view.destination, SafReceiptState.VERIFIED))
        SafRevisionResult(p.view.destination, p.view.afterSha256)
    }
    companion object { const val MAX_BYTES = 65_536 }
}
