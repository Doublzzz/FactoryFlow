# Third-party materials / 第三方材料

This inventory describes the source preview reviewed on 2026-10-23. FactoryFlow uses the [MIT License](LICENSE). Third-party licenses remain applicable independently; the project's MIT license does not replace them.

## Included asset

The unmodified Noto Sans SC variable font at `apps/web/public/fonts/NotoSansSC-Variable.ttf` comes from [Google Fonts](https://github.com/google/fonts/tree/main/ofl/notosanssc). Its copyright notice and SIL Open Font License 1.1 are retained in [OFL-NotoSansSC.txt](apps/web/public/fonts/OFL-NotoSansSC.txt), beside the font. Keep them with redistributed copies. SHA-256 of the included font: `a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da`.

## Declared dependencies

Package sources and versions are locked in `uv.lock` and `package-lock.json`; dependency implementations are not vendored in this source preview. The following direct-dependency license labels were read from freshly installed package metadata. They are an inventory, not replacements for the packages' full license texts or the notices for their dependencies.

| Python package | Version | Declared license |
|---|---|---|
| Alembic | 1.20.0 | MIT |
| FastAPI | 0.142.1 | MIT |
| openpyxl | 3.1.5 | MIT |
| Pillow | 12.1.1 | MIT-CMU |
| psycopg / psycopg-binary | 3.3.6 | LGPL-3.0-only |
| Pydantic | 2.13.5 | MIT |
| pypdfium2 | 5.13.0 | BSD-3-Clause, Apache-2.0 and dependency licenses |
| SQLAlchemy | 2.1.1 | MIT |
| Uvicorn | 0.54.0 | BSD-3-Clause |

pypdfium2 wheels include PDFium and additional build-component notices. The psycopg binary distribution also needs to be considered when redistributing a prepared runtime. A project's MIT or other license would not replace these obligations.

| Node package | Version | Declared license |
|---|---|---|
| React / React DOM | 19.3.0 | MIT |
| openapi-fetch | 0.17.0 | MIT |
| openapi-typescript | 7.13.0 | MIT |
| TypeScript | 5.9.3 | Apache-2.0 |
| Vite | 8.3.1 | MIT |
| @vitejs/plugin-react | 6.1.1 | MIT |
| @types/node | 24.10.1 | MIT |
| @types/react / @types/react-dom | 19.3.0 | MIT |

The lockfiles also include transitive and development dependencies. This limited source review does not claim that every transitive license has been independently audited.

## Separate Windows preview distribution

The source snapshot does not vendor Python/PostgreSQL distributions, installed packages, Microsoft runtime binaries or OCR models. The matching Windows preview includes a package-level inventory and full retained notice files in `app/third-party` and beside each runtime. Third-party components keep their own licenses.

PostgreSQL 18.6 is built from its official source with native MSVC, NLS disabled and static zlib 1.3.1. The EDB distribution and its gettext/iconv/winpthread DLLs are not used. The exact optional FFmpeg video plugin from opencv-python 5.0.0.93 is omitted; still-image/PDF OCR remains supported, and the bundled OpenCV RECORD and installation manifest document the omission. Original OpenCV notices remain intact, including references to components in the untrimmed upstream wheel.

The separate third-party source attachment contains PostgreSQL/zlib source and the build recipe, psycopg 3.3.6, Shapely 2.2.0/GEOS 3.14.1 and its pinned Windows recipe, plus certifi/tqdm source. LGPL/MPL notices remain applicable; there is no restriction on modifying/replacing those libraries or on reverse engineering needed to debug such modifications. The integrity manifest is regenerable from the supplied application/build source and is not DRM.

The installer displays the original Windows CRT conditions and requires explicit acceptance before copying files. Those conditions apply to the Microsoft components, not to FactoryFlow's MIT-licensed source. The optional VC Redistributable EXE is not included.

See [distribution notes](docs/DISTRIBUTION.md) for exact inputs, source correspondence, verification and installation limits. The inventory and tests are engineering evidence, not a blanket legal certification.
