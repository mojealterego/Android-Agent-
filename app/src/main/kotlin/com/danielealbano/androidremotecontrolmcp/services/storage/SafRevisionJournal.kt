package com.danielealbano.androidremotecontrolmcp.services.storage

import java.io.IOException
import java.nio.ByteBuffer
import java.nio.channels.FileChannel
import java.nio.file.Files
import java.nio.file.LinkOption
import java.nio.file.Path
import java.nio.file.StandardCopyOption
import java.nio.file.StandardOpenOption

internal enum class SafReceiptState { PENDING, VERIFIED, ACKNOWLEDGED }
internal data class SafReceipt(val destination: String, val state: SafReceiptState) {
    init { require(destination.matches(Regex("omega-[0-9a-f-]{36}\\.txt"))) }
}

/** Private metadata only; no source path, contents or grants. Single writer under engine mutex. */
internal class SafRevisionJournal(private val path: Path) {
    fun read(): SafReceipt? {
        if (Files.notExists(path, LinkOption.NOFOLLOW_LINKS)) return null
        if (!Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS)) throw IOException("Invalid revision journal")
        FileChannel.open(path, StandardOpenOption.READ, LinkOption.NOFOLLOW_LINKS).use { channel ->
            if (channel.size() !in 1..128) throw IOException("Invalid revision journal")
            val bytes = ByteBuffer.allocate(129)
            while (bytes.hasRemaining() && channel.read(bytes) > 0) { /* bounded */ }
            val text = String(bytes.array(), 0, bytes.position(), Charsets.US_ASCII)
            val parts = text.split('\n')
            if (parts.size != 3 || parts[2].isNotEmpty()) throw IOException("Invalid revision journal")
            return try { SafReceipt(parts[1], SafReceiptState.valueOf(parts[0])) }
            catch (e: IllegalArgumentException) { throw IOException("Invalid revision journal", e) }
        }
    }
    fun write(receipt: SafReceipt) {
        val temp = Files.createTempFile(path.parent, ".omega-revision-", ".tmp")
        try {
            FileChannel.open(temp, StandardOpenOption.WRITE).use { channel ->
                val bytes = ByteBuffer.wrap("${receipt.state.name}\n${receipt.destination}\n".toByteArray(Charsets.US_ASCII))
                while (bytes.hasRemaining()) channel.write(bytes)
                channel.force(true)
            }
            Files.move(temp, path, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
        } finally { Files.deleteIfExists(temp) }
    }
}
