# scripts/ — ビルド & 起動スクリプト

開発者向けのビルド手順と、エンドユーザー向けのダブルクリック起動スクリプトをまとめています。

## ファイル一覧

| ファイル | 用途 | 対象 |
|----------|------|------|
| `build_exe.py` | PyInstaller でスタンドアロン実行ファイル生成 | 開発者 / CI |
| `build_vvpp.py` | VVPP (VOICEVOX エンジンプラグイン) を生成 | 開発者 / CI |
| `smoke_test_local.py` | ローカル起動確認。必要なら共有 vocoder を配置して実歌唱まで検証 | 開発者 |
| `start.bat` | Windows でダブルクリック起動 | エンドユーザー |
| `start.command` | macOS でダブルクリック起動 | エンドユーザー |

## ビルド手順 (開発者向け)

### 1. 依存関係のインストール

```bash
pip install -e .[dev,build]
# Pillow は build_vvpp.py で icon.png のフォールバック生成に使うので必要に応じて
pip install Pillow
```

### 2. 実行ファイルを生成

```bash
python scripts/build_exe.py
# → dist/DiffSingerConnector(.exe)
```

主なオプション:

- `--clean` : PyInstaller のキャッシュを破棄して再ビルド
- `--keep-build` : ビルド中間生成物 `build/` を残す (デフォルトは削除)

### 3. VVPP パッケージを生成

```bash
python scripts/build_vvpp.py
# → dist/DiffSingerConnector-<version>-<os>.vvpp
```

主なオプション:

- `--version 0.1.0` : バージョン文字列を上書き (既定: `pyproject.toml` から取得)
- `--os windows` : ファイル名の OS ラベルを上書き (既定: 実行中 OS から推定)

## OS ごとの注意事項

### Windows

- **VC++ Redistributable**: `onnxruntime` の動作に必要です。Microsoft 配布の最新版を入れてください。
- ビルドは PowerShell / cmd どちらでも可。
- 配布する VVPP のファイル名は `DiffSingerConnector-<version>-windows.vvpp` を推奨。
- アンチウイルスが PyInstaller 製 exe を誤検知することがあります。コードサイニング証明書が無い場合は配布物の SHA256 を README に明記してください。

### macOS

- **コード署名 (codesign) は未対応**: 初回起動時に Gatekeeper のブロックが入ります。ユーザーには「右クリック → 開く」で許可してもらう旨をドキュメントに記載してください。
- universal2 / arm64 対応の onnxruntime を使う場合は環境を分けてビルドしてください。
- `start.command` は配布前に `chmod +x scripts/start.command` を済ませておくこと。

### Linux

- 公式サポート対象外ですが、`build_exe.py` 自体は動作します。配布物のファイル名は `linux` ラベルが付与されます。

## 動作確認

```bash
# 実行ファイルを直接起動
dist/DiffSingerConnector --port 50122

# 別ターミナルから
curl http://127.0.0.1:50122/version
curl http://127.0.0.1:50122/engine_manifest
```

ソースツリー実行時はスモークテストを使うと、起動確認から実歌唱まで一括で検証できます。

```bash
# メタ API だけ確認
.venv/bin/python scripts/smoke_test_local.py

# OpenUtau 共有 vocoder を自動配置し、WAV 生成まで確認
.venv/bin/python scripts/smoke_test_local.py --download-openutau-vocoder --synthesize
```

`--synthesize` 成功時は `logs/smoke_test_song.wav` が生成されます。

## CI

`.github/workflows/release.yml` がタグ push (`v*`) で Windows / macOS の VVPP と単独実行ファイルを GitHub Releases に自動アップロードします。
