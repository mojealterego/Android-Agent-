package com.danielealbano.androidremotecontrolmcp.services.storage

import kotlinx.coroutines.runBlocking
import java.nio.file.Files

private class Fixture : SafRevisionBackend {
    var grant: String? = "grant"
    var source = "original".toByteArray()
    var identity = "source"
    var created = 0
    var writes = 0
    var output: ByteArray? = null
    var revokeOnCreate = false
    var alias = false
    var corrupt = false
    var collide = false
    var rebindOnCreate = false
    override suspend fun access(location: String) = grant
    override suspend fun lookup(location: String, grant: String, name: String): String? = if (name == "report.txt") identity else if (collide || created > 0) "new" else null
    override suspend fun read(location: String, grant: String, id: String): ByteArray = if (id == identity) source.copyOf() else output?.copyOf() ?: byteArrayOf()
    override suspend fun create(location: String, grant: String, name: String): String {
        if (rebindOnCreate) this.grant = "new grant"
        check(this.grant == grant)
        created++
        if (revokeOnCreate) this.grant = null
        return if (alias) identity else "new"
    }
    override suspend fun writeFresh(location: String, grant: String, id: String, bytes: ByteArray) {
        writes++; output = if (corrupt) byteArrayOf(1) else bytes.copyOf()
    }
}

fun main() = runBlocking {
    var count = 0
    suspend fun test(name: String, block: suspend () -> Unit) { block(); count++; println("PASS $name") }
    suspend fun denied(block: suspend () -> Unit) { check(runCatching { block() }.isFailure) }
    test("preview is read-only and output is a separate copy") {
        val f = Fixture(); val e = SafRevisionEngine(f)
        val p = e.preview("loc", "report.txt", "changed")
        check(p.before == "original" && p.after == "changed" && f.created == 0)
        check(e.apply(p.token).destination == p.destination && f.writes == 1 && f.source.decodeToString() == "original")
        check(f.output!!.decodeToString() == "changed")
        denied { e.apply(p.token) }; check(f.created == 1)
    }
    test("source changes or changes identity prevent creation") {
        for (change in listOf<(Fixture)->Unit>({it.source = "new".toByteArray()}, {it.identity = "other"})) {
            val f=Fixture(); val e=SafRevisionEngine(f); val p=e.preview("loc","report.txt","changed"); change(f)
            denied { e.apply(p.token) }; check(f.created==0)
        }
    }
    test("expired approval and replaced preview are denied") {
        var now=1L; val f=Fixture(); val e=SafRevisionEngine(f) { now }
        val p=e.preview("loc","report.txt","changed"); now+=121_000
        denied { e.apply(p.token) }; val a=e.preview("loc","report.txt","a"); e.preview("loc","report.txt","b")
        denied { e.apply(a.token) }; check(f.created==0)
    }
    test("revocation before or after creation fences writes") {
        for (after in listOf(false,true)) {
            val f=Fixture(); val e=SafRevisionEngine(f); val p=e.preview("loc","report.txt","changed")
            if(after) f.revokeOnCreate=true else f.grant=null
            denied { e.apply(p.token) }; check(f.writes==0 && f.created==if(after) 1 else 0)
            denied { e.apply(p.token) }
        }
    }
    test("backend must reject a grant rebound inside create boundary") {
        val f=Fixture(); val e=SafRevisionEngine(f); val p=e.preview("loc","report.txt","changed"); f.rebindOnCreate=true
        denied { e.apply(p.token) }; check(f.created==0 && f.writes==0)
    }
    test("provider alias is never written") {
        val f=Fixture(); val e=SafRevisionEngine(f); val p=e.preview("loc","report.txt","changed"); f.alias=true
        denied { e.apply(p.token) }; check(f.writes==0)
    }
    test("post-write mismatch is not reported as success and not replayed") {
        val f=Fixture(); val e=SafRevisionEngine(f); val p=e.preview("loc","report.txt","changed"); f.corrupt=true
        denied { e.apply(p.token) }; denied { e.apply(p.token) }; check(f.writes==1)
    }
    test("strict text limits and paths") {
        val f=Fixture(); val e=SafRevisionEngine(f)
        for (name in listOf("../report.txt","/report.txt","a\\b.txt","report.jpg",".hidden.txt")) denied { e.preview("loc",name,"changed") }
        denied { e.preview("loc","report.txt","x".repeat(65537)) }; denied { e.preview("loc","report.txt","\uD800") }
        f.source=byteArrayOf(0xff.toByte()); denied { e.preview("loc","report.txt","changed") }; check(f.created==0)
    }
    test("destination collision stops before creation") {
        val f=Fixture(); val e=SafRevisionEngine(f); val p=e.preview("loc","report.txt","changed"); f.collide=true
        denied { e.apply(p.token) }; check(f.created==0)
    }
    test("invalid token cannot authorize and explicit discard invalidates") {
        val f=Fixture(); val e=SafRevisionEngine(f); val p=e.preview("loc","report.txt","changed")
        denied { e.apply("wrong") }; e.discard(); denied { e.apply(p.token) }; check(f.created==0)
    }
    test("pending journal survives restart and fences new plans until explicit acknowledgement") {
        val root = Files.createTempDirectory("saf-receipt")
        try {
            val path = root.resolve("receipt"); val f=Fixture(); val e=SafRevisionEngine(f,SafRevisionJournal(path))
            val p=e.preview("loc","report.txt","changed"); f.revokeOnCreate=true
            denied { e.apply(p.token) }
            val recovered=SafRevisionEngine(f,SafRevisionJournal(path))
            check(recovered.receipt()==SafReceipt(p.destination,SafReceiptState.PENDING))
            f.grant="grant"; f.created=0; f.revokeOnCreate=false
            denied { recovered.preview("loc","report.txt","another") }
            denied { recovered.acknowledge("wrong") }
            recovered.acknowledge(p.destination)
            val next=recovered.preview("loc","report.txt","another")
            recovered.apply(next.token)
            check(recovered.receipt()==SafReceipt(next.destination,SafReceiptState.VERIFIED))
            check(!Files.readString(path).contains("original"))
        } finally { root.toFile().deleteRecursively() }
    }
    test("corrupt receipt fails closed") {
        val root=Files.createTempDirectory("saf-corrupt")
        try {
            val path=root.resolve("receipt"); Files.writeString(path,"invalid")
            val f=Fixture(); val e=SafRevisionEngine(f,SafRevisionJournal(path))
            denied { e.preview("loc","report.txt","changed") }; check(f.created==0)
        } finally { root.toFile().deleteRecursively() }
    }
    println("SAF REVISION CHECKS: $count passed")
}
