#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
lib="$(cd "$(dirname "$(readlink -f "$(command -v kotlinc)")")/../lib" && pwd)"
coroutines="${COROUTINES_JAR:-$lib/kotlinx-coroutines-core-jvm.jar}"
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
src="$root/app/src/main/kotlin/com/danielealbano/androidremotecontrolmcp/services/storage"
kotlinc -cp "$coroutines" "$src/SafRevisionEngine.kt" "$src/SafRevisionJournal.kt" "$root/omega-verification/SafRevisionChecks.kt" -include-runtime -d "$work/checks.jar"
java -cp "$work/checks.jar:$coroutines" com.danielealbano.androidremotecontrolmcp.services.storage.SafRevisionChecksKt
