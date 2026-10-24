# Windows preview distribution

The source snapshot and Windows offline package use the same application source. The source contains no runtime accounts, databases, installed toolchains or old Git history. The prepared release is a developer preview; clean-machine Windows and factory acceptance remain separate.

## Runtime inputs

- Windows CPython 3.14.7 and the locked project Python packages.
- PostgreSQL 18.6 built from the official source with MSVC x64, NLS disabled and zlib 1.3.1 linked statically. ICU, SSL and optional server integrations are disabled. FactoryFlow uses a loopback-only database, UTF8 / locale C and SCRAM authentication. Database command-line diagnostics are English; the application language switch is unchanged.
- The separately prepared RapidOCR 3.9.2 / ONNX Runtime 1.30.0 / Pillow 12.1.1 environment and the three hash-pinned models. opencv-python 5.0.0.93 is retained except its unused FFmpeg video plugin. The builder checks that plugin's original SHA-256 before omitting exactly that file and its output RECORD entry. All other image/OCR libraries and upstream notices remain.
- Web assets compiled from this source snapshot and the complete package-level third-party notices/inventory.

The EDB gettext/iconv/winpthread libraries and the FFmpeg video plugin are not distributed in this preview. Their previous provenance gaps therefore do not block this replacement package. This does not change obligations for the libraries that remain.

## Build

The third-party source attachment includes exact PostgreSQL/zlib archives, SHA-256/source URLs and the native build recipe. Build tools are developer prerequisites; they are not installed on the target factory computer. Source for psycopg, Shapely/GEOS and the pinned GEOS Windows build recipe, certifi and tqdm is provided in the same attachment.

Build the frontend into a new external directory. Assemble the retained license texts, inventory and build notes in a separate notices directory containing README.md and inventory.json. Then run:

```powershell
python scripts/build-offline-package.py --output <new-external-directory> --ocr-base <ocr-python-runtime> --ocr-site <ocr-site-packages> --postgres-root <built-postgres-install> --web-directory <web-build-directory> --notices-directory <reviewed-notice-directory>
```

The PostgreSQL root must contain bin/lib/share and the upstream COPYING file. The builder also supports the old EDB layout for private local verification; using that layout requires its own distribution review and is not the prepared public runtime. The builder checks inputs before copying and rejects existing output directories, ZIPs and build receipts. It records retained files and the single omitted plugin in bundle.json. It does not perform a legal review. Keep the source attachment, notices and checksums alongside the Windows download.

## Verification and limits

Extract the ZIP to a new directory. Read the original Microsoft runtime conditions before running the bundled Python with `-I -X utf8 install.py --destination <new-directory> --no-shortcuts --accept-third-party-terms`. That flag is for explicit automated acceptance; interactive installation displays the original text and requires Y. Refusal or EOF makes no installation or shortcut.

Run `scripts/verify-offline-package.py --app <installed-program> --root <new-synthetic-check-directory>` using only the installed Python. It checks first setup, order/delivery/statement/Excel, packaged OCR, restart and backup/restore. Use new synthetic directories only. Keep passwords, private runtime config, logs and databases outside release artifacts.

The FFmpeg omission is additionally checked with cold independent runtimes on PNG, JPEG and a two-page PDF. All result fields, including text, geometry, previews and CPU/model metadata, must agree before and after. This establishes the tested still-image/PDF behavior, not video support or real-document OCR accuracy.

Check source/application/web equality, archive membership and CRC, hashes, third-party source records and absence of private data. The release notes describe the actual executed checks. No local check establishes clean Windows installation, native Excel pagination, physical printing or factory acceptance. This preview supports a new data directory; it does not offer an in-place upgrade of an existing business database.

LGPL libraries remain replaceable. Rebuild the package and its integrity manifest after changing them; the manifest is not a restriction on modification or debugging. FactoryFlow's MIT license does not replace third-party terms.
