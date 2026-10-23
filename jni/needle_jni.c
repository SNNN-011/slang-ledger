/*
 * Jembatan JNI tipis di atas mesin Needle (libneedle.a untuk Android arm64).
 *
 * Tidak ada logika di sini selain memindahkan string/byte antara Kotlin dan C,
 * supaya kalau mesinnya berubah, yang perlu disesuaikan cuma file ini.
 * Kontrak sisi Kotlin: com.example.data.local.NeedleNative
 *
 * Bangun dengan: build_android/jni/build_android_so.ps1
 */
#include <jni.h>
#include <stdlib.h>
#include <string.h>

#include "needle.h"

/* Sama dengan bawaan Python (needle/__init__.py, buffer_size=65536): jawaban
 * satu function call jauh di bawah ini. */
#define COMPLETE_BUFFER 65536

/* needle_load(cact, n) - model dibaca dari memory, jadi byte-nya dikirim utuh
 * dari Kotlin (aset APK). */
JNIEXPORT jint JNICALL
Java_com_example_data_local_NeedleNative_loadModel(JNIEnv *env, jclass clazz, jbyteArray cact) {
    (void) clazz;
    if (cact == NULL) {
        return -1;
    }
    jsize length = (*env)->GetArrayLength(env, cact);
    if (length <= 0) {
        return -1;
    }
    /* Critical: 63 MB tidak perlu disalin dua kali hanya untuk dibaca. */
    jbyte *bytes = (*env)->GetPrimitiveArrayCritical(env, cact, NULL);
    if (bytes == NULL) {
        return -1;
    }
    int rc = needle_load((const unsigned char *) bytes, (unsigned long long) length);
    (*env)->ReleasePrimitiveArrayCritical(env, cact, bytes, JNI_ABORT);
    return rc;
}

/* needle_init(system_prompt, tools_json, tool_index) - tool_index tidak dipakai
 * (NULL), sama seperti pemakaian di eval. */
JNIEXPORT jint JNICALL
Java_com_example_data_local_NeedleNative_initModel(JNIEnv *env, jclass clazz,
                                                   jstring system, jstring tools) {
    (void) clazz;
    const char *system_utf = NULL;
    const char *tools_utf = NULL;
    if (system != NULL) {
        system_utf = (*env)->GetStringUTFChars(env, system, NULL);
    }
    if (tools != NULL) {
        tools_utf = (*env)->GetStringUTFChars(env, tools, NULL);
    }
    int rc = needle_init(system_utf, tools_utf, NULL);
    if (system_utf != NULL) {
        (*env)->ReleaseStringUTFChars(env, system, system_utf);
    }
    if (tools_utf != NULL) {
        (*env)->ReleaseStringUTFChars(env, tools, tools_utf);
    }
    return rc;
}

/* needle_complete(text, NULL, 0, max_new_tokens, out, cap) - keluaran JSON
 * dikembalikan sebagai string; NULL berarti gagal (isi needle_last_error()). */
JNIEXPORT jstring JNICALL
Java_com_example_data_local_NeedleNative_complete(JNIEnv *env, jclass clazz,
                                                  jstring text, jint max_new_tokens) {
    (void) clazz;
    if (text == NULL) {
        return NULL;
    }
    const char *input = (*env)->GetStringUTFChars(env, text, NULL);
    if (input == NULL) {
        return NULL;
    }
    char *out = (char *) malloc(COMPLETE_BUFFER);
    jstring result = NULL;
    if (out != NULL) {
        memset(out, 0, COMPLETE_BUFFER);
        int rc = needle_complete(input, NULL, 0, (int) max_new_tokens, out, COMPLETE_BUFFER);
        if (rc >= 0) {
            result = (*env)->NewStringUTF(env, out);
        }
        free(out);
    }
    (*env)->ReleaseStringUTFChars(env, text, input);
    return result;
}

JNIEXPORT void JNICALL
Java_com_example_data_local_NeedleNative_reset(JNIEnv *env, jclass clazz) {
    (void) env;
    (void) clazz;
    needle_reset();
}

JNIEXPORT jstring JNICALL
Java_com_example_data_local_NeedleNative_lastError(JNIEnv *env, jclass clazz) {
    (void) clazz;
    const char *message = needle_last_error();
    if (message == NULL) {
        return NULL;
    }
    return (*env)->NewStringUTF(env, message);
}

JNIEXPORT jint JNICALL
Java_com_example_data_local_NeedleNative_models(JNIEnv *env, jclass clazz) {
    (void) env;
    (void) clazz;
    return needle_models();
}
