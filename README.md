# Slang Ledger

> A small on-device model that turns casual, code-mixed Indonesian speech into
> structured finance entries.

Slang Ledger reads one sentence of everyday Indonesian — `"kemarin jajan bakso 25rb"`,
`"dapat transferan dari nyokap 500 ribu"`, `"isi bensin 60rb"` — and returns a
tool call with the amount, direction, item, category, and date. It runs entirely
on the phone: no network, no text ever leaves the device.

- **Size:** 60.5 MB (63,437,076 bytes), `md5 90c128e4187ab114b5f65609a179e7af`
- **Base model:** [Needle](https://github.com/cactus-compute/needle) by Cactus Compute (Apache-2.0)
- **Format:** `.cact`, executed by the Needle engine on Android `arm64-v8a`
- **Training run:** `r10_cat_a` (round 10, category-aware variant)
- **Weights:** [`model/rank64.cact`](model/rank64.cact)

---

## Can I use this in my own finance app?

**Yes — if your app records Indonesian transactions and matches the contract
below.** This is a task-specific model, not a general chatbot. It was trained on
one job: sentence in, one ledger entry out.

What you get for free:

| Capability | Examples it handles |
| :--- | :--- |
| Amount parsing | `25rb`, `1,5 juta`, `20.000.000,-`, `dua ratus ribu`, `1.2jt` |
| Direction | `beli`/`bayar`/`jajan` → expense, `gaji`/`terima`/`dijual` → income |
| Relative dates | `kemarin`, `2 hari lalu`, `tgl 16`, `senin kemarin` |
| Item extraction | `bakso`, `bensin`, `whiskas`, `token listrik` |
| Category selection | picks from **your** category list, sent in the tool schema |

What you do **not** get:

- Receipt photos / OCR — text input only.
- Free-form chat or "why did I spend so much" answers — this model only emits
  tool calls. Pair it with your own rules or a larger model for that.
- Your schema for free. Tool names, argument names, and the prompt shape are
  fixed by training. Change them and accuracy drops (see
  [Adapting it](#adapting-it-to-a-different-schema)).

The model is Indonesian-first. Code-mixed input (`"top up gopay 50k"`,
`"bayar kos 1.2jt"`) works; English-only input is out of distribution.

## The contract

The model was trained with a very specific prompt. Prefixes that differ from
this — a longer system prompt, chat history, tool descriptions, extra tools —
measurably reduce accuracy.

### 1. System prompt: one date line

```
date: 2026-10-22 Thu 08:00
```

Format: `date: yyyy-MM-dd EEE HH:mm`. Nothing else in the system slot.

### 2. Tools: exactly two, in this order

`catat_pengeluaran` first, then `catat_masuk`. The user's own categories go into
the `category` enum, and the JSON is serialized with **no spaces** after `:` or
`,` (the engine renders it with `json.dumps(..., separators=(",", ":"))`).

```json
[{"name":"catat_pengeluaran","parameters":{"type":"object","properties":{"amount":{"type":"integer"},"category":{"type":"string","enum":["Belanja","Hiburan","Makanan","Tagihan","Transportasi"]},"item":{"type":"string"},"date":{"type":"string"}},"required":["category"]}},{"name":"catat_masuk","parameters":{"type":"object","properties":{"amount":{"type":"integer"},"category":{"type":"string","enum":["Freelance","Gaji","Investasi"]},"item":{"type":"string"},"date":{"type":"string"}},"required":["category"]}}]
```

Rules that matter:

- Key order: `name`, then `parameters` → `type`, `properties` → `amount`,
  `category`, `item`, `date`, then `required`.
- `required` is `["category"]` only. `amount` is optional — the model may
  legitimately omit it when the sentence has no number.
- Categories are trimmed, de-duplicated case-insensitively, and **sorted**.
  Keep that order stable; a changing prefix forces a model re-initialization.
- Empty category list → omit `enum` entirely and send `{"type":"string"}`.
  Do not send an empty `enum`.

Reference implementation: [`jni/needle_jni.c`](jni/needle_jni.c) for the bridge,
and the Kotlin builder this contract was extracted from (see
[`docs/PASANG-LOKAL.md`](docs/PASANG-LOKAL.md) for the integration steps).

### 3. Call

```
initModel(system, tools)      // once per day / per category change
reset()                       // before every request — no conversation memory
complete(sentence, 128)       // maxNewTokens = 128 is enough
```

Every request stands alone. Feeding previous turns back in makes the output
worse, not better.

### 4. Output

The engine returns a JSON envelope:

```json
{"function_calls":[{"name":"catat_pengeluaran","arguments":{"amount":25000,"category":"Makanan","item":"bakso","date":"2026-10-21"}}]}
```

An empty `function_calls` array means "no transaction in that sentence". A
non-empty `suppressed_calls` array means the engine dropped a low-confidence
call — treat that as "ask the user", not "record it".

## Adapting it to a different schema

If your app already has its own tool names, argument names, or a much larger
category taxonomy, the honest answer is: **fine-tune it, or wrap it.** The
weights will not map cleanly onto tool names they never saw.

The generator that produced the training data is in
[`training/generate_app_dataset.py`](training/generate_app_dataset.py), with the
tool schema in [`training/tools_app.json`](training/tools_app.json). It covers
Indonesian amount formats, relative dates, direction cues, custom category names,
and negative examples ("no transaction here").

Realistic paths, cheapest first:

1. **Match the contract.** Keep the two tool names and four argument names, put
   your categories in the enum. Zero training, works today.
2. **Translate at the edge.** Keep the model contract, map `catat_masuk` /
   `catat_pengeluaran` onto your own models in your app layer.
3. **Fine-tune.** Reuse the generator with your schema. Expect hours of training
   and a fresh evaluation set — see [`docs/UJI_HP.md`](docs/UJI_HP.md).

## Files

| Path | What it is |
| :--- | :--- |
| `model/rank64.cact` | The weights used in production (60.5 MB) |
| `model/rank64.cact.md5` | Checksum |
| `jni/needle_jni.c` | Thin JNI bridge (Kotlin ↔ C), no business logic |
| `jni/build_android_so.ps1` | Builds `libneedle_jni.so` for Android arm64 |
| `training/generate_app_dataset.py` | Dataset generator (amounts, dates, categories, negatives) |
| `training/generate_dataset.py` | Generic variant of the generator |
| `training/tools_app.json` | Tool schema the model was trained against |
| `eval/eval_clean_599.jsonl` | 599 held-out Indonesian sentences |
| `eval/eval_app_sim.jsonl` | App-shaped evaluation set |
| `docs/PASANG-LOKAL.md` | Original installation notes (Indonesian) |
| `docs/PENJELASAN-OTAK-V5.md` | Design notes on the training rounds (Indonesian) |
| `docs/UJI_HP.md` | On-device test log and pitfalls (Indonesian) |

## Integration

1. Copy the weights into your Android app:
   ```
   app/src/main/assets/rank64.cact
   ```
2. Build the JNI bridge against the upstream Needle engine for Android arm64:
   ```
   jni/build_android_so.ps1
   ```
3. Copy the result:
   ```
   app/src/main/jniLibs/arm64-v8a/libneedle_jni.so
   ```
4. Load the model, send the date line + two-tool schema, then call
   `complete()` with the user's sentence.

The engine binaries are **not** in this repo — see below.

## What is not included, and why

| Missing | Reason |
| :--- | :--- |
| `libneedle.a`, `needle3.cact`, `libneedle_jni.so` | Cactus engine artifacts. The engine carries its own source-available license, which is not Apache-2.0, so it is not redistributed here. Build or obtain it from the upstream Needle project. |
| Training data (`*.jsonl` beyond the eval sets) | Generated locally from personal finance sentences; not published. Regenerate with `training/generate_app_dataset.py`. |
| Losing checkpoints (`r5_rank128_a`, `rank64_r8e1`) | Only the winner is kept. |

## Evaluation

On-device test (not just unit tests), 50 fresh Indonesian sentences:

| Check | Result |
| :--- | :--- |
| Sentence recorded | 50/50 |
| Direction (income/expense) | 50/50 |
| Amount | 50/50 |
| Category | 47/50 |

The three misses were category edge cases: a race prize, an insurance payout,
and a parking fine. 116 JVM unit tests pass in the reference app. Details in
[`docs/UJI_HP.md`](docs/UJI_HP.md).

## Limitations

- Text only, Indonesian informal/code-mixed only.
- Built and tested on `arm64-v8a`; no other ABI is provided.
- Single transaction per sentence. "Beli kopi 20rb dan rokok 30rb" will only
  yield one entry.
- Category accuracy depends on the enum you send. Categories that never appeared
  during training rely on keyword fallbacks; long tail names are the main error
  source.
- The prefix must stay short. Adding context degrades output.

## License

- **Model weights** (`model/rank64.cact`) are a fine-tune of Needle, licensed
  **Apache-2.0** by Cactus Compute:
  <https://github.com/cactus-compute/needle/blob/main/LICENSE>
- **Source in this repo** (`jni/`, `training/`, `eval/`, `docs/`) is **MIT** —
  see [LICENSE](LICENSE).
- **Cactus engine** artifacts are not distributed here and remain under their
  own license.
