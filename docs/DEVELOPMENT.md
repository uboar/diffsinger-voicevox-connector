# 開発者向けドキュメント

> **対象読者**: 本コネクターのソースコードを触ってみたい開発者向けです。一般利用者は [INSTALL.md](INSTALL.md) をご覧ください。

---

## 必要環境

- Python 3.11
- Git
- （配布物ビルド時のみ）Windows もしくは macOS の実機環境

---

## セットアップ

```bash
git clone https://github.com/<owner>/diffsinger-voicevox-connector.git
cd diffsinger-voicevox-connector
pip install -e .[dev]
```

> 仮想環境（`python -m venv .venv` など）の利用を推奨します。

---

## ローカル起動

```bash
PYTHONPATH=src .venv/bin/python -m diffsinger_engine --port 50122 --models ./models
```

起動後、以下で動作確認できます。

```bash
curl http://127.0.0.1:50122/version
curl http://127.0.0.1:50122/engine_manifest
curl http://127.0.0.1:50122/singers
```

または、起動から疎通確認までまとめて行うスモークテストを使えます。

```bash
.venv/bin/python scripts/smoke_test_local.py
```

実モデルで実際に歌わせる確認まで行う場合は、共有 vocoder (`nsf_hifigan`) を自動配置しつつ
WAV 生成まで確認できます。

```bash
.venv/bin/python scripts/smoke_test_local.py --download-openutau-vocoder --synthesize
```

成功すると `logs/smoke_test_song.wav` が生成されます。OpenUtau 形式モデルで
`vocoder: nsf_hifigan` のような共有 vocoder 参照を使っている場合は、
`models/vocoders/` に `.onnx` または `.oudep` を置くと自動解決されます。

`.venv` がある場合は `scripts/start.command` / `scripts/start.bat` もその仮想環境を優先し、
ソースツリー実行時は自動で `src/` を `PYTHONPATH` に追加します。

VOICEVOX エディタの「設定」→「エンジン」→「ホストを追加」で `http://127.0.0.1:50122` を登録すると、ビルド済み `.vvpp` を使わずにエディタから接続できます。

### 開発時のおすすめ手順

1. `.venv/bin/python scripts/smoke_test_local.py --download-openutau-vocoder --synthesize`
2. `pytest tests/`
3. `PYTHONPATH=src .venv/bin/python -m diffsinger_engine --port 50122 --models ./models`
4. VOICEVOX エディタの「設定」→「エンジン」→「ホストを追加」で `http://127.0.0.1:50122` を登録
5. VOICEVOX のソング画面で DiffSinger 歌手を選び、実際に再生確認

---

## テスト

```bash
pytest tests/
```

主なテスト対象:

- `tests/test_g2p.py` — ひらがな→音素変換
- `tests/test_score_converter.py` — VOICEVOX Score → DiffSinger 入力
- `tests/test_api_meta.py` / `tests/test_api_sing.py` — HTTP API スキーマ・挙動

---

## 配布物ビルド

スタンドアロン実行ファイル化と VVPP パッケージ化は別スクリプトに分かれています。

```bash
python scripts/build_exe.py     # PyInstaller で実行ファイルを作成
python scripts/build_vvpp.py    # 上記成果物を含む .vvpp パッケージを作成
```

成果物は `dist/` 配下に生成されます。macOS ではビルドした CPU に応じて
`DiffSingerConnector-<version>-macos-arm64.vvpp` または
`DiffSingerConnector-<version>-macos-x64.vvpp` が生成されます。

### macOS でローカルビルドする手順

Apple Silicon / Intel のどちらでも、その Mac 自身でビルドした成果物を配布用に使う想定です。
まず自分の CPU 種別を確認します。

```bash
uname -m
# arm64   -> Apple Silicon 用の成果物が生成される
# x86_64  -> Intel Mac 用の成果物が生成される
```

初回のみ、必要であれば Xcode Command Line Tools を入れてください。

```bash
xcode-select --install
```

その後、仮想環境を作って依存関係を入れます。

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .[dev,build]
pip install Pillow
```

ビルドは次の 2 コマンドです。

```bash
python scripts/build_exe.py --clean
python scripts/build_vvpp.py
```

生成物は `dist/` に出ます。

```bash
ls -lh dist/
# Apple Silicon なら DiffSingerConnector-<version>-macos-arm64.vvpp
# Intel Mac なら   DiffSingerConnector-<version>-macos-x64.vvpp
```

必要なら、配布前に単体起動で疎通確認できます。

```bash
dist/DiffSingerConnector --port 50122
# 別ターミナルで
curl http://127.0.0.1:50122/version
```

補足:

- `macos-arm64` の VVPP は Apple Silicon Mac 上でビルド
- `macos-x64` の VVPP は Intel Mac 上でビルド
- universal2 にはしていないため、1 台で両方を同時生成する前提ではありません
- コード署名は未対応なので、macOS 側で初回起動時に Gatekeeper の確認が出ることがあります

---

## 設計の詳細

アーキテクチャ全体像、API 設計、各モジュールの責務などは設計計画書を参照してください。

- 設計計画書: `~/.claude/plans/expressive-churning-perlis.md`

---

## 貢献について

不具合報告・機能要望は GitHub Issues へ、コードの変更提案は Pull Request にてお願いします。

---

## 次に読むべき記事

- 利用者向けクイックスタート → [../README.md](../README.md)
- API の対象エンドポイント一覧 → 設計計画書
