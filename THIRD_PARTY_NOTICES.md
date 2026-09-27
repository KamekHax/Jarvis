# Third-Party Notices

JARVIS Local includes or can optionally download third-party software and model assets. These components are **not** relicensed under JARVIS Local's MIT license. Keep their own license and notices with redistributions; verify each model/asset's terms before repackaging it.

## Optional English neural voices (downloaded only after user action)

- **Kokoro int8 ONNX model and speaker embeddings** — Apache License 2.0. Upstream model card: <https://huggingface.co/NeuML/kokoro-int8-onnx>. The project model card identifies the underlying Kokoro-82M model and the source of the exported model and voice assets. Model assets are downloaded from a fixed upstream revision and checked against SHA-256 hashes before use.
- **`ttstokenizer` 1.1.0** — Apache License 2.0. Source and license: <https://github.com/neuml/ttstokenizer>. It supplies English text-to-IPA tokenization for local ONNX inference; it does not require eSpeak. Its package declares `anyascii`, `inflect`, `numpy`, and `nltk` dependencies.
- **NLTK English tokenizer data** — the MIT-licensed English averaged-perceptron tagger is downloaded from <https://github.com/nltk/nltk_data>; the CMU Pronouncing Dictionary is also distributed there. CMUdict permits unrestricted research and commercial use and requests acknowledgment of its origin. See the upstream [CMUdict license](https://github.com/cmusphinx/cmudict/blob/master/LICENSE) and the NLTK data package records for [the tagger](https://github.com/nltk/nltk_data/blob/gh-pages/packages/taggers/averaged_perceptron_tagger_eng.xml) and [CMUdict](https://github.com/nltk/nltk_data/blob/gh-pages/packages/corpora/cmudict.xml).
- **ONNX Runtime 1.20.1** — MIT License. Source and license: <https://github.com/microsoft/onnxruntime>.
- The implementation downloads only the listed model/speaker files, tokenizer packages, and the stated English tokenizer data after the user presses **Install**. It then performs inference on the user's computer; spoken text is not sent to the model host or an inference service.

## Other runtime dependencies

JARVIS uses separately licensed third-party Python packages and operating-system-provided components. Their terms apply independently; consult the respective package metadata and upstream license before redistributing them. In particular, the Windows standalone build bundles its runtime dependencies, so redistributors should retain each included license/notice from the dependency distributions.

## Project licensing

JARVIS Local's own source code is available under the MIT License in `LICENSE`. This notice is informational and does not replace any included license or the upstream licenses linked above.
