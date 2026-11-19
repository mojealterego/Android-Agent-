package com.danielealbano.androidremotecontrolmcp.services.storage

import android.content.Context
import android.net.Uri
import android.provider.DocumentsContract
import android.provider.DocumentsContract.Document
import com.danielealbano.androidremotecontrolmcp.data.repository.SettingsRepository
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import java.io.ByteArrayOutputStream

/** Explicit local ExternalStorageProvider tree only, no arbitrary URI or generic provider mutation. */
internal class AndroidSafRevisionBackend(
    private val context: Context,
    private val settings: SettingsRepository,
    private val locations: StorageLocationProvider,
) : SafRevisionBackend {
    private val resolver get() = context.contentResolver

    private suspend fun tree(location: String): Uri? {
        val perms = settings.getServerConfig().toolPermissionsConfig
        if (!listOf("read_file", "write_file").all(perms::isToolEnabled) || !locations.isWriteAllowed(location)) return null
        val uri = locations.getTreeUriForLocation(location) ?: return null
        if (uri.scheme != "content" || uri.authority != "com.android.externalstorage.documents" || !DocumentsContract.isTreeUri(uri)) return null
        if (!resolver.persistedUriPermissions.any { it.uri == uri && it.isReadPermission && it.isWritePermission }) return null
        return uri
    }
    override suspend fun access(location: String): String? = tree(location)?.toString()
    private suspend fun requireTree(location: String, grant: String): Uri {
        val current = tree(location) ?: throw SecurityException("SAF revision denied")
        if (current.toString() != grant) throw SecurityException("SAF grant changed")
        return current
    }
    private fun childId(tree: Uri, name: String): String {
        require(name.isNotBlank() && name != "." && name != ".." && '/' !in name && '\\' !in name && name.none { it.isISOControl() })
        val root = DocumentsContract.getTreeDocumentId(tree)
        return root + (if (root.endsWith(":")) "" else "/") + name
    }
    private fun document(tree: Uri, id: String): Uri {
        val root = DocumentsContract.getTreeDocumentId(tree)
        val prefix = root + if (root.endsWith(":")) "" else "/"
        require(id.startsWith(prefix) && id.length > prefix.length)
        require(id == childId(tree, id.removePrefix(prefix)))
        return DocumentsContract.buildDocumentUriUsingTree(tree, id)
    }
    override suspend fun lookup(location: String, grant: String, name: String): String? {
        val tree = requireTree(location, grant)
        val expected = childId(tree, name)
        val children = DocumentsContract.buildChildDocumentsUriUsingTree(tree, DocumentsContract.getTreeDocumentId(tree))
        val columns = arrayOf(Document.COLUMN_DOCUMENT_ID, Document.COLUMN_DISPLAY_NAME, Document.COLUMN_MIME_TYPE)
        var match: String? = null
        resolver.query(children, columns, null, null, null)?.use { cursor ->
            var count = 0
            while (cursor.moveToNext()) {
                currentCoroutineContext().ensureActive()
                check(++count <= 4096) { "Too many directory entries" }
                if (cursor.getString(1) == name) {
                    check(match == null && cursor.getString(0) == expected && cursor.getString(2) != Document.MIME_TYPE_DIR) { "Ambiguous document" }
                    match = expected
                }
            }
        } ?: error("Directory listing unavailable")
        check(requireTree(location, grant) == tree) { "SAF grant changed" }
        return match
    }
    override suspend fun read(location: String, grant: String, id: String): ByteArray {
        val tree = requireTree(location, grant)
        val uri = document(tree, id)
        val output = ByteArrayOutputStream()
        resolver.openInputStream(uri)?.use { input ->
            val buffer = ByteArray(4096)
            while (true) {
                currentCoroutineContext().ensureActive()
                val n = input.read(buffer)
                if (n < 0) break
                check(n > 0 && output.size() + n <= SafRevisionEngine.MAX_BYTES) { "Document read exceeds limit" }
                output.write(buffer, 0, n)
            }
        } ?: error("Document unavailable")
        check(requireTree(location, grant) == tree) { "SAF grant changed" }
        return output.toByteArray()
    }
    override suspend fun create(location: String, grant: String, name: String): String {
        val tree = requireTree(location, grant)
        check(name.matches(Regex("omega-[0-9a-f-]{36}\\.txt")))
        check(lookup(location, grant, name) == null && requireTree(location, grant) == tree)
        val parent = DocumentsContract.buildDocumentUriUsingTree(tree, DocumentsContract.getTreeDocumentId(tree))
        val created = DocumentsContract.createDocument(resolver, parent, "text/plain", name) ?: error("Document creation failed")
        check(created.authority == tree.authority && DocumentsContract.getDocumentId(created) == childId(tree, name)) { "Unexpected new document identity" }
        return DocumentsContract.getDocumentId(created)
    }
    override suspend fun writeFresh(location: String, grant: String, id: String, bytes: ByteArray) {
        val tree = requireTree(location, grant)
        val name = id.substringAfterLast('/').substringAfterLast(':')
        check(name.matches(Regex("omega-[0-9a-f-]{36}\\.txt")) && id == childId(tree, name) && bytes.size <= SafRevisionEngine.MAX_BYTES)
        check(lookup(location, grant, name) == id && read(location, grant, id).isEmpty() && requireTree(location, grant) == tree)
        currentCoroutineContext().ensureActive()
        // Caller has just created this exact empty document; never write the original.
        resolver.openOutputStream(document(tree, id), "w")?.use { it.write(bytes); it.flush() } ?: error("New document write failed")
    }
}
