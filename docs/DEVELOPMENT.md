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

`.venv` がある場合は `scripts/start.command` / `scripts/start.bat` もその仮想環境を優先し、
ソースツリー実行時は自動で `src/` を `PYTHONPATH` に追加します。

VOICEVOX エディタの「設定」→「エンジン」→「ホストを追加」で `http://127.0.0.1:50122` を登録すると、ビルド済み `.vvpp` を使わずにエディタから接続できます。

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

成果物は `dist/` 配下に生成されます。

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
