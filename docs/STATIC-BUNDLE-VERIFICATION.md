# Static project bundle verification

The Studio exports an editable project specification and generated static files in a ZIP. In Studio, open **Reopen a verified static project ZIP**, choose the file and select **Verify and reopen ZIP**. After verification you may download the evidence or explicitly confirm replacing the current draft; cancellation leaves the draft untouched. Changing the selected file invalidates the displayed evidence. The local server verifies the original ZIP without extracting or executing its contents.

For command-line use, verify a bundle before extracting or opening it:

```sh
python scripts/creator_bundle.py creator-project.zip --report bundle-evidence.json
```

This standard-library check accepts a Creator Studio ZIP up to 4 MiB, verifies its exact member list, validates the structured draft and manifest, and compares generated file bytes with the current generator. It rejects duplicate, missing, unexpected, encrypted or special-file entries. It never extracts or executes archive contents, contacts a network service, or overwrites an evidence file.

The evidence contains SHA-256 fingerprints of the archive, canonical project specification and generated files. The verification establishes consistency with the current generator; it is not a signature, proof of authorship, browser test, or publication approval. A modified specification and consistently regenerated bundle can pass. Old exports may fail after generator changes; rebuild from the reviewed project JSON when appropriate.

Use the separate [release readiness workflow](RELEASE-READINESS.md) for browser and human review. Authenticated, relational and other backend bundles have separate formats and are not supported by this verifier.
