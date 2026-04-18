# DiffSinger Connector for VOICEVOX

VOICEVOX エディタから **DiffSinger（オープンソースの歌声合成エンジン）** を呼び出して歌わせるための「中継ぎソフト」です。VOICEVOX 本体には一切手を加えず、VOICEVOX 公式の「マルチエンジン機能」に追加するだけで、いつもの歌唱画面に DiffSinger の歌手が増えます。

> 「DiffSinger（ディフシンガー）」とは、研究者やコミュニティが公開している AI による歌声合成エンジンの一種です。本コネクターを通すことで、VOICEVOX エディタの操作感のままで利用できるようになります。

---

## はじめてのかたへ：やることは 3 つだけ

1. **VOICEVOX を最新版にしてください**
   公式サイト（<https://voicevox.hiroshiba.jp/>）から最新版のインストーラーをダウンロードして上書きインストールしてください。
2. **自分の環境に合う `.vvpp` をダブルクリック**
   GitHub のリリースページから配布ファイルをダウンロードしてください。Windows は `DiffSingerConnector-<version>-windows.vvpp`、Apple Silicon Mac は `DiffSingerConnector-<version>-macos-arm64.vvpp`、Intel Mac は `DiffSingerConnector-<version>-macos-x64.vvpp` を選びます。ダブルクリックすると VOICEVOX が自動で起動し、「エンジンを追加しますか？」と聞かれるので「はい」を押すだけで導入完了です。
3. **DiffSinger 用の歌手モデルを `models/` フォルダに置く**
   モデルの入手方法と置き場所は [docs/MODEL_SETUP.md](docs/MODEL_SETUP.md) に画像付きで案内しています。

導入が終わったら、いつもどおり VOICEVOX エディタの「ソング（歌う）」画面を開き、歌手リストから DiffSinger 系の歌手を選んでお楽しみください。

詳しい手順は [docs/INSTALL.md](docs/INSTALL.md) をご覧ください。

---

## 動作画面

![VOICEVOX エディタで DiffSinger 歌手を選んでいる様子](docs/images/screenshot_overview.png)

![ソング画面で歌詞を入力して再生している様子](docs/images/screenshot_singing.png)

> 画像は実際の動作イメージです。バージョンや OS によって見た目が多少異なります。

---

## 対応モデル

本コネクターは **openvpi/DiffSinger 形式の日本語モデル** に対応しています。

- **形式**: `dsconfig.yaml` と `acoustic.onnx`、`vocoder.onnx`、`phonemes.txt` が含まれた、いわゆる「OpenUtau 互換 DiffSinger モデル」
- **言語**: 日本語（ひらがな歌詞）を想定
- **サンプリングレート**: モデルが 44.1kHz 出力でもエディタ側 24kHz でも自動で調整されます

> **ONNX（オニキス）= AI モデルを保存するための、業界で広く使われている標準的なファイル形式です。** 本コネクターはこの形式のモデルを読み込んで歌声を生成します。

モデル自体は本コネクターには **同梱されていません**。各モデル配布元の利用規約に従ってご自身で入手してください。詳しくは [docs/MODEL_SETUP.md](docs/MODEL_SETUP.md) を参照してください。

---

## 困ったときは

- 歌手リストに出てこない / 音が出ない / 起動が遅い、などの症状は [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) をご覧ください。
- それでも解決しない場合は、`logs/connector.log` を添えて GitHub の Issues にご報告ください。報告用のテンプレートも上記ドキュメントに用意してあります。

---

## ライセンス

本コネクター本体のソースコードは **MIT ライセンス** です。詳細は `resources/terms.md` をご覧ください。

DiffSinger 本体や、本コネクターが利用している各種オープンソースソフトウェアにはそれぞれのライセンスが適用されます。利用者の皆さまが配置する DiffSinger モデルは、各モデル配布元の利用規約が別途適用されます（商用利用可否・二次配布可否・クレジット表記義務など）ので、必ずご確認のうえお使いください。

---

## クレジット

- 歌声合成エンジン: [openvpi/DiffSinger](https://github.com/openvpi/DiffSinger) コミュニティの皆さま
- ホストアプリ: [VOICEVOX](https://voicevox.hiroshiba.jp/)（ヒホ氏 / VOICEVOX 開発チーム）
- 日本語音素解析: [pyopenjtalk](https://github.com/r9y9/pyopenjtalk)
- 各モデルの開発・配布をされているコミュニティ（OpenUtau / DiffSinger 日本語ボイスバンク開発者の皆さま）

すばらしいオープンソースの上に成り立っているプロジェクトです。改めて感謝申し上げます。

---

## 開発者の方へ

ソースコードからのビルドや内部設計、貢献方法は [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) にまとめています。
