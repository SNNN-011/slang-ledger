# build_android_so.ps1 - bangun libneedle_jni.so (Android arm64) dari libneedle.a.
#
# Pakai: powershell -NoProfile -ExecutionPolicy Bypass -File build_android/jni/build_android_so.ps1
#
# Butuh: NDK (folder berisi toolchains/llvm) dan JDK 17 (untuk jni.h).
# Hasil: build_android/jni/out/arm64-v8a/libneedle_jni.so
# Salin hasil itu ke: Nano-Money/app/src/main/jniLibs/arm64-v8a/

$ErrorActionPreference = "Stop"
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent   # ...\needle-nanomoney
$jniDir = $PSScriptRoot
$engine = Join-Path $root "build_android\android-arm64"
$outDir = Join-Path $jniDir "out\arm64-v8a"

# NDK: dari env, dari folder NDK di dalam SDK Android, atau dari folder temp.
$ndk = $env:ANDROID_NDK_HOME
if (-not $ndk) {
    $sdkNdk = "C:\Users\yasin\AppData\Local\Android\Sdk\ndk"
    if (Test-Path $sdkNdk) {
        $ndk = (Get-ChildItem $sdkNdk -Directory | Sort-Object Name -Descending | Select-Object -First 1).FullName
    }
}
if (-not $ndk) {
    $tmpNdk = Get-ChildItem "C:\Users\yasin\AppData\Local\Temp\opencode" -Directory -Filter "android-ndk-*" -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending | Select-Object -First 1
    if ($tmpNdk) { $ndk = $tmpNdk.FullName }
}
if (-not $ndk -or -not (Test-Path $ndk)) { throw "NDK tidak ditemukan. Set ANDROID_NDK_HOME." }

$clang = Join-Path $ndk "toolchains\llvm\prebuilt\windows-x86_64\bin\aarch64-linux-android26-clang.cmd"
if (-not (Test-Path $clang)) { throw "clang NDK tidak ada: $clang" }
if (-not (Test-Path (Join-Path $engine "libneedle.a"))) { throw "libneedle.a tidak ada di $engine (jalankan: needle download android-arm64 --out build_android)" }

$javaHome = $env:JAVA_HOME
if (-not $javaHome) { $javaHome = "C:\Program Files\Microsoft\jdk-17.0.20.8-hotspot" }
$jdkInclude = Join-Path $javaHome "include"
if (-not (Test-Path (Join-Path $jdkInclude "jni.h"))) { throw "jni.h tidak ada di $jdkInclude" }

# Catatan: jni.h TIDAK diambil dari JDK. Versi JDK memakai jni_md.h platform
# Windows (__declspec) yang ditolak clang untuk target Android. NDK sudah
# membawa jni.h di dalam sysroot-nya, dan itu yang dipakai.
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$soPath = Join-Path $outDir "libneedle_jni.so"

& $clang -shared -O2 -fvisibility=hidden `
    -o $soPath `
    (Join-Path $jniDir "needle_jni.c") `
    (Join-Path $engine "libneedle.a") `
    -I $engine `
    '-Wl,--gc-sections' '-Wl,--no-undefined' `
    -lc++_static -lc++abi -llog -lm
if ($LASTEXITCODE -ne 0) { throw "clang gagal (exit $LASTEXITCODE)" }

"OK -> $soPath ($((Get-Item $soPath).Length) B)"
